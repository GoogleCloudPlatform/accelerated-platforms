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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../../../../")"

# shellcheck disable=SC1091
source "${MY_PATH}/../../config/huggingface.sh"

if [[ ! -v ACCELERATOR_TYPE ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!"
  exit 1
fi

DYNAMO_MODE="${DYNAMO_MODE:-kv-routing}"
DYNAMO_VARIANT_SUFFIX="${DYNAMO_VARIANT_SUFFIX:-}"

if [[ -v HF_MODEL_ID && -n "${HF_MODEL_ID}" ]]; then
  models=("${HF_MODEL_ID}")
else
  # shellcheck disable=SC2154
  models=("${hf_gpu_dynamo_trtllm_models[@]}")
fi

for model in "${models[@]}"; do
  export HF_MODEL_ID=${model}
  # shellcheck disable=SC1091
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  base_variant_dir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/dynamo-trtllm/${DYNAMO_MODE}/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  variant_dir="${base_variant_dir}${DYNAMO_VARIANT_SUFFIX}"
  if [[ -d "${variant_dir}" ]]; then
    echo "Testing '${HF_MODEL_ID}' NVIDIA Dynamo (${DYNAMO_MODE}${DYNAMO_VARIANT_SUFFIX}) deployment on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"

    NAME_SUFFIX="$(awk '$1 == "nameSuffix:" { print $2 }' "${base_variant_dir}/kustomization.yaml")"
    SERVED_MODEL_NAME="$(awk -F= '$1 == "MODEL_ID" { print $2 }' "${base_variant_dir}/runtime.env")"

    # shellcheck disable=SC2154
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/dynamo-etcd${NAME_SUFFIX}" --timeout=600s
    if [[ "${DYNAMO_MODE}" == "disaggregated-pd" ]]; then
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/dynamo-trtllm-prefill${NAME_SUFFIX}" --timeout=1200s
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/dynamo-trtllm-decode${NAME_SUFFIX}" --timeout=1200s
    else
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/dynamo-trtllm-worker${NAME_SUFFIX}" --timeout=1200s
    fi
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/dynamo-frontend${NAME_SUFFIX}" --timeout=600s

    echo "Setting up port forwarding..."
    port_forwarding_failed=0
    forwarding_port=$(shuf -i 49152-65535 -n 1)
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" port-forward "service/dynamo-frontend${NAME_SUFFIX}" "${forwarding_port}:8000" >/dev/null &
    PF_PID=$!

    echo "Waiting for port forwarding..."
    attempts=0
    while ! echo -e '\x1dclose\x0d' | telnet localhost "${forwarding_port}" >/dev/null 2>&1; do
      if ! kill -0 "${PF_PID}" 2>/dev/null; then
        port_forwarding_failed=1
        echo "Port forwarding process exited!"
        echo
        break
      fi
      attempts=$((attempts + 1))
      if [[ ${attempts} -ge 300 ]]; then
        port_forwarding_failed=1
        echo "Timed out waiting for port forwarding!"
        kill -9 "${PF_PID}" 2>/dev/null || true
        break
      fi

      sleep 0.1
    done

    if [[ ${port_forwarding_failed} == 1 ]]; then
      exit 1
    fi

    echo "Sending GET request to '/v1/models'"
    echo "----------------------------------------------------------------------------------"
    curl --fail --request GET --show-error --silent "http://127.0.0.1:${forwarding_port}/v1/models" | jq -e '.data | length > 0'
    sleep 1
    echo "----------------------------------------------------------------------------------"
    echo

    echo "Sending POST request to '/v1/chat/completions'"
    echo "----------------------------------------------------------------------------------"
    curl "http://127.0.0.1:${forwarding_port}/v1/chat/completions" \
      --data '{
        "model": "'"${SERVED_MODEL_NAME}"'",
        "messages": [ { "role": "user", "content": "Why is the sky blue?" } ],
        "max_tokens": 512
      }' \
      --fail \
      --header "Content-Type: application/json" \
      --request POST \
      --show-error \
      --silent | jq -e '(.choices[0].message.content // .choices[0].message.reasoning_content) | length > 0'
    echo "----------------------------------------------------------------------------------"

    kill -9 "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
    echo
  else
    echo "'${HF_MODEL_ID}' model does not have a '${DYNAMO_MODE}' configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
