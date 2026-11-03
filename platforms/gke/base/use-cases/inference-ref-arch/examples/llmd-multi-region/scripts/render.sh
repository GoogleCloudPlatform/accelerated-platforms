#!/usr/bin/env bash
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Rendering helpers. Source this file after lib.sh.
#
# Templates (*.tpl.yaml) under manifests/ are rendered with envsubst into
# ${MR_WORK_DIR}/rendered/<region_key>/, never into the repository, so that the
# checkout stays clean and every region can be rendered independently.

# Only these variables are substituted. Anything else that looks like a shell
# variable (for example, the Kubernetes $(VAR) syntax) is left untouched.
MR_TEMPLATE_VARS='${MR_HPA_RUNNING_METRIC} ${MR_HPA_TARGET_RUNNING} ${MR_POD_SNAPSHOTS_BUCKET} ${MR_GPU_MACHINE_TYPE} ${MR_ACCELERATOR_TYPE} ${MR_HPA_MAX_REPLICAS} ${MR_HPA_METRIC} ${MR_HPA_TARGET_AVERAGE} ${MR_GPU_HOLD_IMAGE} ${MR_LLMD_GIT_REF} ${MR_REPLICAS_PER_REGION} ${MR_NAMESPACE} ${MR_COMPUTE_CLASS} ${MR_VLLM_IMAGE} ${MR_GPU_COUNT} ${MR_MODELS_BUCKET} ${MR_MODEL_PATH} ${MR_SERVED_MODEL_NAME} ${MR_TENSOR_PARALLEL_SIZE} ${MR_MAX_MODEL_LEN} ${MR_GPU_MEMORY_UTILIZATION} ${MR_GATEWAY_NAME} ${MR_GATEWAY_ADDRESSES} ${MR_ROUTE_BACKEND_GROUP} ${MR_ROUTE_BACKEND_KIND} ${MR_ROUTE_BACKEND_NAME} ${MR_ROUTE_BACKEND_PORT} ${MR_LB_MAX_UTILIZATION_PERCENT} ${MR_LB_PREFERRED_REGION} ${MR_BACKEND_TIMEOUT_SEC} ${MR_NEG_PREFIX}'
export MR_GATEWAY_NAME="${MR_GATEWAY_NAME:-llm-mr-gateway}"
export MR_BACKEND_TIMEOUT_SEC="${MR_BACKEND_TIMEOUT_SEC:-3600}"

# mr_render_dir <src_dir> <dst_dir>
# Copies src_dir to dst_dir, rendering *.tpl.yaml files to *.yaml.
mr_render_dir() {
  local src="${1}" dst="${2}"
  rm -rf "${dst}"
  mkdir -p "${dst}"
  (cd "${src}" && find . -type d -exec mkdir -p "${dst}/{}" \;)
  while IFS= read -r -d '' f; do
    local rel="${f#"${src}"/}"
    if [[ "${rel}" == *.tpl.yaml ]]; then
      envsubst "${MR_TEMPLATE_VARS}" <"${f}" >"${dst}/${rel%.tpl.yaml}.yaml"
    else
      cp "${f}" "${dst}/${rel}"
    fi
  done < <(find "${src}" -type f -print0)
}

# mr_render_model_server <region_key>
# Renders the model server manifests for one region and prints the directory.
mr_render_model_server() {
  local key="${1}"
  local dst="${MR_WORK_DIR}/rendered/${key}/model-server"
  (
    MR_MODELS_BUCKET="$(mr_models_bucket "${key}")"
    MR_NEG_PREFIX="$(mr_neg_prefix "${key}")"
    MR_COMPUTE_CLASS="$(mr_compute_class "${key}")"
    MR_POD_SNAPSHOTS_BUCKET="$(mr_pod_snapshots_bucket "${key}")"
    export MR_MODELS_BUCKET MR_NEG_PREFIX MR_COMPUTE_CLASS MR_POD_SNAPSHOTS_BUCKET
    mr_render_dir "${MR_EXAMPLE_DIR}/manifests/model-server" "${dst}"
  )
  # The ServiceExport is only needed (and its CRD only exists) when the
  # multi-cluster Gateway fleet feature is used.
  if [[ "${MR_GLOBAL_LB}" != "mc-gateway" ]]; then
    sed -i '/serviceexport.yaml/d' "${dst}/baseline/kustomization.yaml"
  fi
  echo "${dst}"
}

# Short name of a router release, used in NEG and backend names.
mr_router_short_name() {
  case "${1}" in
  precise-prefix-cache-routing) echo "ppcr" ;;
  optimized-baseline) echo "ob" ;;
  *) echo "${1}" ;;
  esac
}

# Router releases deployed in every region. Both select the llm-d arm pods.
export MR_LLMD_ROUTER_RELEASES="${MR_LLMD_ROUTER_RELEASES:-precise-prefix-cache-routing optimized-baseline}"

# Optional override of the prefix-cache-affinity-filter peakPrefillThroughput
# (tokens/s). Upstream calibrated it for Qwen3-32B on H100 80 GB with TP=2; use
# the llm-d calibration recipe to measure the value for other accelerators.
export MR_LLMD_PEAK_PREFILL_THROUGHPUT="${MR_LLMD_PEAK_PREFILL_THROUGHPUT:-}"

# mr_fetch_llmd_values
# Downloads the router values files at the pinned llm-d commit into a local
# cache and prints the cache directory.
mr_fetch_llmd_values() {
  local cache="${MR_WORK_DIR}/llmd/${MR_LLMD_GIT_REF}"
  local base_url="https://raw.githubusercontent.com/llm-d/llm-d/${MR_LLMD_GIT_REF}/guides"
  mkdir -p "${cache}"
  local f
  for f in \
    recipes/router/base.values.yaml \
    recipes/router/features/monitoring-gke.values.yaml \
    precise-prefix-cache-routing/router/precise-prefix-cache-routing.values.yaml \
    optimized-baseline/router/optimized-baseline.values.yaml; do
    if [[ ! -s "${cache}/${f}" ]]; then
      mkdir -p "$(dirname "${cache}/${f}")"
      curl -fsSL --retry 3 "${base_url}/${f}" -o "${cache}/${f}" || return 1
    fi
  done
  echo "${cache}"
}

# mr_pull_router_chart
# Pulls the pinned router chart for the configured global load balancer mode,
# verifies its OCI digest, and prints the path of the unpacked chart.
mr_pull_router_chart() {
  local chart_ref="${MR_LLMD_ROUTER_CHART}" digest="${MR_LLMD_ROUTER_CHART_DIGEST}"
  if [[ "${MR_GLOBAL_LB}" != "mc-gateway" ]]; then
    chart_ref="${MR_LLMD_ROUTER_STANDALONE_CHART}"
    digest="${MR_LLMD_ROUTER_STANDALONE_CHART_DIGEST}"
  fi
  local chart_name="${chart_ref##*/}"
  local dir="${MR_WORK_DIR}/llmd/chart-${chart_name}-${MR_LLMD_ROUTER_CHART_VERSION}"
  if [[ ! -f "${dir}/${chart_name}/Chart.yaml" ]]; then
    rm -rf "${dir}"
    mkdir -p "${dir}"
    local out
    out="$(helm pull "${chart_ref}" --version "${MR_LLMD_ROUTER_CHART_VERSION}" --untar --untardir "${dir}" 2>&1)" || {
      echo "${out}" >&2
      return 1
    }
    if [[ -n "${digest}" ]] && ! grep -q "Digest: ${digest}" <<<"${out}"; then
      echo "router chart digest mismatch: expected ${digest}, got: ${out}" >&2
      rm -rf "${dir}"
      return 1
    fi
  fi
  echo "${dir}/${chart_name}"
}

# mr_render_router <region_key> <release>
# Renders one llm-d router release (InferencePool + EPP) for a region and
# prints the path of the rendered manifest.
mr_render_router() {
  local key="${1}" release="${2}"
  local cache chart dst guide_values
  cache="$(mr_fetch_llmd_values)" || return 1
  chart="$(mr_pull_router_chart)" || return 1
  dst="${MR_WORK_DIR}/rendered/${key}/router"
  mkdir -p "${dst}"

  guide_values="${dst}/${release}.guide.values.yaml"
  # The token-producer tokenizer model name must match the served model name.
  sed "s|modelName: Qwen/Qwen3-32B|modelName: ${MR_SERVED_MODEL_NAME}|" \
    "${cache}/${release}/router/${release}.values.yaml" >"${guide_values}"
  if [[ -n "${MR_LLMD_PEAK_PREFILL_THROUGHPUT}" ]]; then
    if grep -q "peakPrefillThroughput:" "${guide_values}"; then
      sed -i "s|peakPrefillThroughput: [0-9]*|peakPrefillThroughput: ${MR_LLMD_PEAK_PREFILL_THROUGHPUT}|" "${guide_values}"
    else
      sed -i "s|- type: prefix-cache-affinity-filter$|- type: prefix-cache-affinity-filter\n          parameters:\n            peakPrefillThroughput: ${MR_LLMD_PEAK_PREFILL_THROUGHPUT}|" "${guide_values}"
    fi
  fi

  helm template "${release}" "${chart}" \
    --namespace "${MR_NAMESPACE}" \
    -f "${cache}/recipes/router/base.values.yaml" \
    -f "${cache}/recipes/router/features/monitoring-gke.values.yaml" \
    -f "${guide_values}" \
    -f "${MR_EXAMPLE_DIR}/manifests/router/values-multi-region.yaml" \
    --set-string "router.epp.image.tag=${MR_LLMD_EPP_IMAGE_TAG}" \
    --set-string "router.epp.image.pullPolicy=IfNotPresent" \
    --set-string "router.proxy.presets.envoy.image=${MR_LLMD_ENVOY_IMAGE}" \
    >"${dst}/${release}.yaml" || return 1
  echo "${dst}/${release}.yaml"
}
