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

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../../../../../)"

source "${MY_PATH}/../../config/huggingface.sh"

if [[ ! -v ACCELERATOR_TYPE ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!"
  exit 1
fi

echo "Model(s) deployed on ${ACCELERATOR_TYPE}"
echo

for model in "${hf_tpu_vllm_models[@]}"; do
  export HF_MODEL_ID=${model}
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  if [[ -d "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" ]]; then
    echo "Testing '${HF_MODEL_ID}' model deployment..."
    echo "--------------------------------------------------------------------------------------------"
    echo "Sourcing environment configuration..."
    source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
    echo "Configuring the deployment..."
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/configure_vllm.sh"
    echo "Setting up port forwarding..."
    kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
    PF_PID=$!
    while ! echo -e '\x1dclose\x0d' | telnet localhost 8000 >/dev/null 2>&1; do
      sleep 0.1
    done
    echo "Sending GET request to '/v1/models'"
    echo "----------------------------------------------------------------------------------"
    curl --request GET --show-error --silent http:/127.0.0.1:8000/v1/models | jq
    sleep 1
    echo "----------------------------------------------------------------------------------"
    echo
    echo "Sending POST request to '/v1/chat/completions'"
    echo "----------------------------------------------------------------------------------"
    curl http://127.0.0.1:8000/v1/chat/completions \
    --data '{
      "model": "/gcs/'${HF_MODEL_ID}'",
      "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
      }' \
    --header "Content-Type: application/json" \
    --request POST \
    --show-error \
    --silent | jq
    echo "----------------------------------------------------------------------------------"
    kill -9 ${PF_PID}
    wait ${PF_PID} 2>/dev/null
    echo
    echo
    echo
    echo
    echo
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
