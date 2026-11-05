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

# Removes an experiment arm from every region (or scales it to zero), so that
# its GPU nodes are released between benchmark sessions.
#
# Usage: delete-arm.sh <baseline|llmd> [--scale-to-zero | --hold-gpus]
#
#   --hold-gpus  keep the arm's GPU nodes with placeholder pods
#                (manifests/common/gpu-hold), for the next arm. The cluster
#                autoscaler removes empty GPU nodes within about a minute, and
#                getting them back can fail during a stockout. deploy-arm.sh
#                releases them. Without this flag, any placeholder is removed.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"
# shellcheck source=/dev/null
source "${MY_PATH}/render.sh"

arm="${1:?usage: delete-arm.sh <baseline|llmd> [--scale-to-zero | --hold-gpus]}"
mode="${2:-delete}"
[[ "${mode}" =~ ^(delete|--scale-to-zero|--hold-gpus)$ ]] || mr_die "unknown argument: ${mode}"
[[ "${arm}" == "baseline" || "${arm}" == "llmd" ]] || mr_die "arm must be one of: baseline, llmd"

delete_arm() {
  local key="${1}"
  local deployment="precise-prefix-cache-routing-gpu-vllm-decode-${arm}"
  local existing_rc=""
  existing_rc="$(mr_kubectl "${key}" get deploy "${deployment}" -n "${MR_NAMESPACE}" \
    -o jsonpath='{.spec.template.spec.runtimeClassName}' 2>/dev/null || true)"
  if [[ -z "${existing_rc}" && "${MR_POD_SNAPSHOTS_ENABLED}" == "true" && "${arm}" == "llmd" ]]; then
    existing_rc="gvisor"
  fi
  # The HPA would scale the arm back up.
  mr_kubectl "${key}" delete hpa -l "acp-mr/arm=${arm}" -n "${MR_NAMESPACE}" --ignore-not-found || true
  if [[ "${mode}" == "--scale-to-zero" ]]; then
    mr_kubectl "${key}" scale deploy "${deployment}" -n "${MR_NAMESPACE}" --replicas=0 || true
    return 0
  fi
  if [[ "${arm}" == "llmd" ]]; then
    local release file
    for release in ${MR_LLMD_ROUTER_RELEASES}; do
      file="${MR_WORK_DIR}/rendered/${key}/router/${release}.yaml"
      [[ -f "${file}" ]] || file="$(mr_render_router "${key}" "${release}")"
      mr_kubectl "${key}" delete -f "${file}" --ignore-not-found --wait=true || true
    done
  fi
  local rendered="${MR_WORK_DIR}/rendered/${key}/model-server/${arm}.rendered.yaml"
  if [[ ! -f "${rendered}" ]]; then
    local dir
    dir="$(mr_render_model_server "${key}")"
    kustomize build "${dir}/${arm}" >"${rendered}"
  fi
  mr_kubectl "${key}" delete -f "${rendered}" --ignore-not-found --wait=true
  if [[ "${mode}" == "--hold-gpus" ]]; then
    # Create the placeholders as soon as the model server pods are gone (so
    # that they aren't pending, which would trigger a scale-up), before the
    # autoscaler considers the GPU nodes unneeded.
    mr_kubectl "${key}" wait --for=delete pod -l "acp-mr/arm=${arm}" -n "${MR_NAMESPACE}" --timeout=900s || true
    local dst="${MR_WORK_DIR}/rendered/${key}/common"
    MR_COMPUTE_CLASS="$(mr_compute_class "${key}")" mr_render_dir "${MR_EXAMPLE_DIR}/manifests/common" "${dst}"
    if [[ -n "${existing_rc}" ]]; then
      # GKE Sandbox nodes are tainted for gVisor pods only: the placeholders
      # need the same runtime class as the arm's pods to stay on them.
      kubectl patch --local -f "${dst}/gpu-hold.yaml" --type merge -o yaml \
        -p "{\"spec\":{\"template\":{\"spec\":{\"runtimeClassName\":\"${existing_rc}\"}}}}" >"${dst}/gpu-hold.patched.yaml"
      mv "${dst}/gpu-hold.patched.yaml" "${dst}/gpu-hold.yaml"
    fi
    mr_kubectl "${key}" apply -f "${dst}/gpu-hold.yaml"
  else
    mr_kubectl "${key}" delete deployment gpu-hold -n "${MR_NAMESPACE}" --ignore-not-found
  fi
}

# Succeeds when a candidate backend still has a standalone NEG in every
# platform registered in shared_network.
backend_has_negs_everywhere() {
  local candidate="${1}" registry negs missing
  registry="$(mr_registry_json)" || return 1
  [[ "${registry}" != "{}" ]] || return 1
  negs="$(gcloud compute network-endpoint-groups list \
    --project="${MR_PROJECT_ID}" \
    --filter="name ~ ^${MR_RESOURCE_NAME_PREFIX}-" \
    --format=json)" || return 1
  missing="$(jq -r \
    --argjson negs "${negs}" \
    --arg prefix "${MR_RESOURCE_NAME_PREFIX}" \
    --arg network_name "$(mr_shared_network_name)" \
    --arg backend "${candidate}" '
    [$negs[] | select(.network | endswith("/networks/" + $network_name)) | .name] as $names
    | [to_entries[] | .key as $p | select(($names | index("\($prefix)-\($p)-\($backend)")) == null) | $p]
    | join(" ")' <<<"${registry}")"
  [[ -z "${missing}" ]]
}

# Detach the arm's NEGs from the Terraform-managed load balancer first, so that
# GKE can delete them together with the Services. If the other arm still has
# NEGs in every registered region, re-apply global_lb without the deleted arm;
# otherwise destroy global_lb cleanly (the next deploy-arm.sh / set-route.sh
# recreates it).
if [[ "${mode}" != "--scale-to-zero" && "${MR_GLOBAL_LB}" != "mc-gateway" ]] && mr_tf_state_has_resources global_lb; then
  lb_state_file="${MR_WORK_DIR}/terraform/global_lb.state.json"
  [[ -f "${lb_state_file}" ]] || lb_state_file="${MR_RESULTS_DIR}/gateway/active.json"
  active_backend="baseline"
  active_mode="locality"
  active_preferred_key="${MR_CONFIG_CLUSTER_KEY}"
  if [[ -f "${lb_state_file}" ]]; then
    active_backend="$(jq -r '.backend // "baseline"' "${lb_state_file}")"
    active_mode="$(jq -r '.lb_mode // "locality"' "${lb_state_file}")"
    active_preferred_key="$(jq -r '.preferred_key // empty' "${lb_state_file}")"
  fi

  fallback_backend=""
  if [[ "${arm}" == "baseline" ]]; then
    for candidate in "${active_backend}" ppcr ob; do
      [[ "${candidate}" == "ppcr" || "${candidate}" == "ob" ]] || continue
      if backend_has_negs_everywhere "${candidate}"; then
        fallback_backend="${candidate}"
        break
      fi
    done
  else
    if backend_has_negs_everywhere "baseline"; then
      fallback_backend="baseline"
    fi
  fi

  if [[ -n "${fallback_backend}" ]]; then
    lb_args=(--backend "${fallback_backend}" --lb-mode "${active_mode}" --no-wait)
    if [[ "${active_mode}" == "preferred" ]]; then
      [[ -n "${active_preferred_key}" ]] ||
        mr_die "${lb_state_file} doesn't record the preferred region; run set-route.sh --lb-mode preferred --preferred-region <key> first"
      lb_args+=(--preferred-region "${active_preferred_key}")
    fi
    MR_LB_EXCLUDE_ARM="${arm}" "${MY_PATH}/set-route.sh" "${lb_args[@]}"
  else
    mr_log "No remaining backend has NEGs in every region; destroying global_lb to detach ${arm} NEGs until the next set-route.sh"
    mr_stage "global_lb_destroy/${arm}" "global" "${MR_MULTI_REGION_DIR}/global_lb.sh" destroy
    rm -f "${MR_RESULTS_DIR}/gateway/active.json" "${MR_RESULTS_DIR}/gateway/vips.json" \
      "${MR_WORK_DIR}/terraform/global_lb.state.json" "${MR_WORK_DIR}/terraform/global_lb.vips.json"
  fi
fi

for key in ${MR_REGION_KEYS}; do
  mr_stage "arm_delete/${arm}" "region/${key}" delete_arm "${key}"
done
