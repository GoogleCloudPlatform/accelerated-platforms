#!/usr/bin/env bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Shared helpers for the online-inference-gpu/<engine>/deployment_*.sh scripts.
# Source this file; don't execute it. Callers set:
#   IRA_GPU_ENGINE_DIR     Overlay parent directory relative to
#                          kubernetes-manifests/online-inference-gpu (for example
#                          `trtllm` or `dynamo-trtllm/kv-routing`).
#   IRA_GPU_CONFIGURE      Configure script relative to the same directory.
#   IRA_GPU_SERVICE        Name (before nameSuffix) of the Service that serves the
#                          OpenAI-compatible API.
#   IRA_GPU_MODELS         Array of default Hugging Face model IDs.
# and optionally:
#   IRA_GPU_VARIANT_SUFFIX Appended to `<ACCELERATOR_TYPE>-<model name>` to select a
#                          variant overlay (for example `-podsnapshot`).
# Workload and Service names are read from the rendered overlay, so the helpers
# work for any nameSuffix and any number of Deployments or StatefulSets.

# shellcheck disable=SC2154 # ira_* variables come from set_environment_variables.sh.
IRA_GPU_COMMON_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 || exit 1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${IRA_GPU_COMMON_DIR}/../../../../../../../../")"
export ACP_REPO_DIR
IRA_GPU_MANIFESTS_DIR="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu"

# shellcheck disable=SC1091
source "${IRA_GPU_COMMON_DIR}/../config/huggingface.sh"

if [[ ! -v ACCELERATOR_TYPE ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!" >&2
  exit 1
fi

IRA_GPU_PF_PID=""
ira_gpu_stop_port_forward() {
  if [[ -n "${IRA_GPU_PF_PID}" ]]; then
    kill "${IRA_GPU_PF_PID}" 2>/dev/null || true
    wait "${IRA_GPU_PF_PID}" 2>/dev/null || true
    IRA_GPU_PF_PID=""
  fi
}
trap ira_gpu_stop_port_forward EXIT

# ira_gpu_for_each_variant <function>
# Calls <function> <variant_dir> for HF_MODEL_ID, or for every model in
# IRA_GPU_MODELS when HF_MODEL_ID is unset, after loading the platform
# environment variables for that model. Models without an overlay are skipped.
ira_gpu_for_each_variant() {
  local callback="${1:?Usage: ira_gpu_for_each_variant <function>}"
  local models=()
  if [[ -v HF_MODEL_ID && -n "${HF_MODEL_ID}" ]]; then
    models=("${HF_MODEL_ID}")
  else
    models=("${IRA_GPU_MODELS[@]}")
  fi

  local model variant_dir
  for model in "${models[@]}"; do
    export HF_MODEL_ID="${model}"
    # shellcheck disable=SC1091
    source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

    variant_dir="${IRA_GPU_MANIFESTS_DIR}/${IRA_GPU_ENGINE_DIR}/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}${IRA_GPU_VARIANT_SUFFIX:-}"
    if [[ -d "${variant_dir}" ]]; then
      echo "${IRA_GPU_ENGINE_DIR}/${variant_dir##*/}: '${HF_MODEL_ID}' on '${ACCELERATOR_TYPE}'"
      echo "--------------------------------------------------------------------------------------------"
      "${callback}" "${variant_dir}"
      echo
    else
      echo "'${HF_MODEL_ID}' has no '${IRA_GPU_ENGINE_DIR}' overlay '${ACCELERATOR_TYPE}-${HF_MODEL_NAME}${IRA_GPU_VARIANT_SUFFIX:-}', skipping."
      echo
    fi
  done
}

ira_gpu_configure() {
  "${IRA_GPU_MANIFESTS_DIR}/${IRA_GPU_ENGINE_DIR%%/*}/${IRA_GPU_CONFIGURE}"
}

ira_gpu_apply() {
  local variant_dir="${1:?variant_dir}" policy
  ira_gpu_configure
  local policies=()
  mapfile -t policies < <(ira_gpu_rendered_names "${variant_dir}" PodSnapshotPolicy)
  if [[ ${#policies[@]} -gt 0 ]]; then
    # Apply storage configs and policies before the Deployment so that on an
    # already-warm gVisor GPU node, the Pod does not start before its
    # PodSnapshotPolicy reconciles Ready=True.
    kubectl kustomize "${variant_dir}" | awk '
      function flush() {
        if (doc != "" && (kind == "PodSnapshotStorageConfig" || kind == "PodSnapshotPolicy")) {
          printf "---\n%s", doc
        }
        doc = ""
        kind = ""
      }
      /^---$/ { flush(); next }
      {
        doc = doc $0 "\n"
        if ($0 ~ /^kind: /) { kind = $2 }
      }
      END { flush() }
    ' | kubectl apply -f -
    for policy in "${policies[@]}"; do
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" \
        wait --for=condition=Ready "podsnapshotpolicy/${policy}" --timeout=120s
    done
  fi
  kubectl apply --kustomize "${variant_dir}"
}

ira_gpu_delete() {
  local variant_dir="${1:?variant_dir}" name policy snapshots
  local kubectl_ns=(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}")
  ira_gpu_configure
  local policies=()
  mapfile -t policies < <(ira_gpu_rendered_names "${variant_dir}" PodSnapshotPolicy)
  if [[ ${#policies[@]} -gt 0 ]]; then
    # Delete the Deployments and PodSnapshotPolicies before the PodSnapshots, so
    # that terminating or running Pods cannot trigger a new snapshot.
    while read -r name; do
      [[ -n "${name}" ]] && "${kubectl_ns[@]}" delete "deployment/${name}" --ignore-not-found
    done < <(ira_gpu_rendered_names "${variant_dir}" Deployment)
  fi
  kubectl delete --ignore-not-found --kustomize "${variant_dir}"
  for policy in "${policies[@]}"; do
    snapshots="$("${kubectl_ns[@]}" get podsnapshots \
      --output=jsonpath="{range .items[?(@.spec.policyName==\"${policy}\")]}{.metadata.name}{\" \"}{end}")"
    if [[ -n "${snapshots}" ]]; then
      # shellcheck disable=SC2086
      "${kubectl_ns[@]}" delete podsnapshots ${snapshots} --ignore-not-found
    fi
  done
}

# ira_gpu_rendered_names <variant_dir> <kind>
# Prints the metadata.name of every <kind> object rendered by the overlay.
ira_gpu_rendered_names() {
  kubectl kustomize "${1:?variant_dir}" | awk -v want="${2:?kind}" '
    /^---/ { kind = ""; in_meta = 0; next }
    /^kind: / { kind = $2; next }
    /^metadata:/ { in_meta = 1; next }
    /^[^ ]/ { in_meta = 0 }
    in_meta && /^  name: / && kind == want { print $2; in_meta = 0 }
  '
}

# ira_gpu_runtime_value <variant_dir> <key>
ira_gpu_runtime_value() {
  awk -F= -v key="${2:?key}" '$1 == key { print substr($0, length(key) + 2) }' "${1:?variant_dir}/runtime.env"
}

# ira_gpu_wait_ready <variant_dir>
# Waits for every StatefulSet, then every Deployment, rendered by the overlay.
ira_gpu_wait_ready() {
  local variant_dir="${1:?variant_dir}" kind name
  for kind in StatefulSet Deployment; do
    while read -r name; do
      [[ -n "${name}" ]] || continue
      echo "Waiting for ${kind,,} '${name}' to become ready..."
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "${kind,,}/${name}" --timeout=1800s
    done < <(ira_gpu_rendered_names "${variant_dir}" "${kind}")
  done
}

# ira_gpu_wait_pod_snapshot <app_label>
# Waits until the PodSnapshot of the PodSnapshotPolicy that selects
# app=<app_label> reports AllSnapshotsAvailable.
ira_gpu_wait_pod_snapshot() {
  local app="${1:?app_label}" policy snapshots
  local kubectl_ns=(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}")
  policy="$("${kubectl_ns[@]}" get podsnapshotpolicies \
    --output=jsonpath="{range .items[?(@.spec.selector.matchLabels.app==\"${app}\")]}{.metadata.name}{\"\\n\"}{end}" | head -1)"
  if [[ -z "${policy}" ]]; then
    echo "No PodSnapshotPolicy selects app=${app}!" >&2
    return 1
  fi
  echo "Waiting for a PodSnapshot of policy '${policy}' to reach AllSnapshotsAvailable..."
  for _ in $(seq 1 80); do
    snapshots="$("${kubectl_ns[@]}" get podsnapshots \
      --output=jsonpath="{range .items[?(@.spec.policyName==\"${policy}\")]}{.metadata.name}{\" \"}{.status.conditions[?(@.type==\"Ready\")].reason}{\"\\n\"}{end}")"
    if grep -q "AllSnapshotsAvailable" <<<"${snapshots}"; then
      echo "PodSnapshot ready: ${snapshots}"
      return 0
    fi
    sleep 15
  done
  echo "Timed out waiting for a PodSnapshot of policy '${policy}' to reach AllSnapshotsAvailable!" >&2
  return 1
}

# ira_gpu_smoke_test <variant_dir>
# Port-forwards to the overlay's IRA_GPU_SERVICE Service and checks
# /v1/models and /v1/chat/completions.
ira_gpu_smoke_test() {
  local variant_dir="${1:?variant_dir}" service="" name port local_port served_model_name
  while read -r name; do
    if [[ "${name}" == "${IRA_GPU_SERVICE}" || "${name}" == "${IRA_GPU_SERVICE}-"* ]]; then
      service="${name}"
    fi
  done < <(ira_gpu_rendered_names "${variant_dir}" Service)
  if [[ -z "${service}" ]]; then
    echo "The overlay renders no '${IRA_GPU_SERVICE}' Service!" >&2
    return 1
  fi
  served_model_name="$(ira_gpu_runtime_value "${variant_dir}" MODEL_ID)"

  local endpoint_pod endpoint_port request_body runtime_class="" target
  request_body="$(jq -n --arg model "${served_model_name}" '{
    model: $model,
    messages: [{role: "user", content: "Why is the sky blue?"}],
    max_tokens: 128,
    temperature: 0,
    chat_template_kwargs: {enable_thinking: false}
  }')"

  endpoint_pod="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get endpoints "${service}" --output=jsonpath='{.subsets[0].addresses[0].targetRef.name}' 2>/dev/null || true)"
  endpoint_port="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get endpoints "${service}" --output=jsonpath='{.subsets[0].ports[0].port}' 2>/dev/null || true)"
  if [[ -n "${endpoint_pod}" && -n "${endpoint_port}" ]]; then
    target="pod/${endpoint_pod}"
    port="${endpoint_port}"
    runtime_class="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get pod "${endpoint_pod}" --output=jsonpath='{.spec.runtimeClassName}' 2>/dev/null || true)"
  else
    target="service/${service}"
    port="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get service "${service}" --output=jsonpath='{.spec.ports[0].port}')"
  fi

  if [[ "${runtime_class}" == "gvisor" ]]; then
    # gVisor's user-space network stack does not bind container listeners on
    # 127.0.0.1 inside the host network namespace that `kubectl port-forward` dials.
    echo "Running in-sandbox smoke test against ${endpoint_pod}:${port} (RuntimeClass=gvisor)..."
    echo "GET /v1/models"
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" exec "${endpoint_pod}" -- \
      curl --fail --request GET --show-error --silent "http://127.0.0.1:${port}/v1/models" | jq -e '.data | length > 0'
    echo "POST /v1/chat/completions"
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" exec "${endpoint_pod}" -- \
      curl "http://127.0.0.1:${port}/v1/chat/completions" \
      --data "${request_body}" \
      --fail \
      --header "Content-Type: application/json" \
      --request POST \
      --show-error \
      --silent | jq -e '(.choices[0].message.content // .choices[0].message.reasoning_content) | length > 0'
    return 0
  fi

  local_port="$(shuf -i 49152-65535 -n 1)"
  echo "Port-forwarding 127.0.0.1:${local_port} to ${target}:${port}..."
  kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" port-forward "${target}" "${local_port}:${port}" >/dev/null &
  IRA_GPU_PF_PID=$!

  local attempts=0
  while ! curl --fail --silent --max-time 2 "http://127.0.0.1:${local_port}/v1/models" >/dev/null 2>&1; do
    if ! kill -0 "${IRA_GPU_PF_PID}" 2>/dev/null; then
      echo "Port forwarding process exited!" >&2
      return 1
    fi
    attempts=$((attempts + 1))
    if [[ ${attempts} -ge 300 ]]; then
      echo "Timed out waiting for port forwarding!" >&2
      ira_gpu_stop_port_forward
      return 1
    fi
    sleep 0.1
  done

  echo "GET /v1/models"
  curl --fail --request GET --show-error --silent "http://127.0.0.1:${local_port}/v1/models" | jq -e '.data | length > 0'

  echo "POST /v1/chat/completions"
  curl "http://127.0.0.1:${local_port}/v1/chat/completions" \
    --data "${request_body}" \
    --fail \
    --header "Content-Type: application/json" \
    --request POST \
    --show-error \
    --silent | jq -e '(.choices[0].message.content // .choices[0].message.reasoning_content) | length > 0'

  ira_gpu_stop_port_forward
}
