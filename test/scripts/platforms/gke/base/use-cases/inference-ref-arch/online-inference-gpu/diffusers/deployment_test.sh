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

for model in "${hf_gpu_diffusers_models[@]}"; do
  export HF_MODEL_ID=${model}
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  if [[ -d "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" ]]; then
    echo "Testing '${HF_MODEL_ID}' model deployment on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"

    echo "Sourcing environment configuration..."
    source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

    echo "Configuring the deployment..."
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/configure_diffusers.sh"

    echo "Setting up port forwarding..."
    port_forwarding_failed=0
    forwarding_port=$(shuf -i 49152-65535 -n 1)
    kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} ${forwarding_port}:8000 >/dev/null &
    PF_PID=$!

    echo "Waiting for port forwarding..."
    while ! echo -e '\x1dclose\x0d' | telnet localhost ${forwarding_port} >/dev/null 2>&1; do
      if ! ps | grep " $PF_PID " >/dev/null; then
        port_forwarding_failed=1
        echo "Port forwarding process exited!"
        echo
        break
      fi

      sleep 0.1
    done

    if [[ ${port_forwarding_failed} == 1 ]] ; then
      break
    fi

    echo "Sending POST request to '/generate'"
    echo "----------------------------------------------------------------------------------"
    curl http://127.0.0.1:${forwarding_port}/generate \
    --data '{
      "height": 512,
      "num_inference_steps": 4,
      "prompt": "A photo of a dog playing fetch in a park.",
      "width": 512
    }' \
    --header "Content-Type: application/json" \
    --output ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png \
    --request POST \
    --show-error \
    --silent
    sleep 1
    ls -alh ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png
    echo "----------------------------------------------------------------------------------"
    echo

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
