#!/usr/bin/env bash

# Copyright 2025 Google LLC
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

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit 1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../../../../")"

source "${MY_PATH}/../../config/huggingface.sh"

if [[ -z "${ACCELERATOR_TYPE:-}" ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!" >&2
  exit 1
fi

PF_PID=""
cleanup_port_forward() {
  if [[ -n "${PF_PID}" ]]; then
    kill "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
    PF_PID=""
  fi
}
trap cleanup_port_forward EXIT

if [[ -v HF_MODEL_ID && -n "${HF_MODEL_ID}" ]]; then
  models=("${HF_MODEL_ID}")
else
  models=("${hf_gpu_vllm_models[@]}")
fi

for model in "${models[@]}"; do
  export HF_MODEL_ID="${model}"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  overlay_dir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  if [[ -d "${overlay_dir}" ]]; then
    echo "Testing '${HF_MODEL_ID}' model deployment on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"

    echo "Setting up port forwarding..."
    forwarding_port="$(shuf -i 49152-65535 -n 1)"
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" port-forward --address 127.0.0.1 "service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" "${forwarding_port}:8000" >/dev/null &
    PF_PID=$!

    echo "Waiting for health check over port-forward..."
    port_forwarding_ready=0
    for _ in $(seq 1 120); do
      if ! kill -0 "${PF_PID}" 2>/dev/null; then
        echo "[ERROR] Port forwarding process (${PF_PID}) exited unexpectedly!" >&2
        exit 1
      fi
      if curl --fail --silent --max-time 2 "http://127.0.0.1:${forwarding_port}/health" >/dev/null 2>&1; then
        port_forwarding_ready=1
        break
      fi
      sleep 0.5
    done

    if [[ "${port_forwarding_ready}" -ne 1 ]]; then
      echo "[ERROR] Timed out waiting for http://127.0.0.1:${forwarding_port}/health" >&2
      exit 1
    fi

    echo "Sending GET request to '/v1/models'"
    echo "----------------------------------------------------------------------------------"
    curl --fail --request GET --show-error --silent "http://127.0.0.1:${forwarding_port}/v1/models" | jq -e '.data | length > 0'
    echo "----------------------------------------------------------------------------------"
    echo

    echo "Sending POST request to '/v1/chat/completions'"
    echo "----------------------------------------------------------------------------------"
    request_body="$(jq -cn --arg model "/gcs/${HF_MODEL_ID}" '{"model": $model, "messages": [{"role": "user", "content": "Why is the sky blue?"}]}')"
    curl "http://127.0.0.1:${forwarding_port}/v1/chat/completions" \
      --data "${request_body}" \
      --fail \
      --header "Content-Type: application/json" \
      --request POST \
      --show-error \
      --silent | jq -e '(.choices[0].message.content // .choices[0].message.reasoning_content) | length > 0'
    echo "----------------------------------------------------------------------------------"
    echo

    cleanup_port_forward
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
