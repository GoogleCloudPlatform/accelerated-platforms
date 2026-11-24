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
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../../../../")"

source "${MY_PATH}/../../config/huggingface.sh"

if [[ -z "${ACCELERATOR_TYPE:-}" ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!" >&2
  exit 1
fi

# Stop the port forwarding process when a command fails and errexit ends the script.
PF_PID=""
trap 'if [[ -n "${PF_PID}" ]]; then kill -9 "${PF_PID}" 2>/dev/null || true; fi' EXIT

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
    forwarding_port=$(shuf -i 49152-65535 -n 1)
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" port-forward --address 127.0.0.1 "service/diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" "${forwarding_port}:8000" >/dev/null &
    PF_PID=$!

    echo "Waiting for health check over port-forward..."
    port_forwarding_ready=0
    for _ in $(seq 1 120); do
      if ! kill -0 "${PF_PID}" 2>/dev/null; then
        echo "[ERROR] Port forwarding process (${PF_PID}) exited unexpectedly!" >&2
        exit 1
      fi
      if curl --fail --silent "http://127.0.0.1:${forwarding_port}/health" >/dev/null 2>&1; then
        port_forwarding_ready=1
        break
      fi
      sleep 0.5
    done

    if [[ "${port_forwarding_ready}" -ne 1 ]]; then
      echo "[ERROR] Timed out waiting for http://127.0.0.1:${forwarding_port}/health" >&2
      kill -9 "${PF_PID}" 2>/dev/null || true
      wait "${PF_PID}" 2>/dev/null || true
      exit 1
    fi

    output_png="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png"
    rm -f "${output_png}"

    if [[ "${HF_MODEL_ID}" == "black-forest-labs/flux.2-klein-4b" ]]; then
      echo "Sending POST request to '/v1/images/generations' (SGLang backend)"
      echo "----------------------------------------------------------------------------------"
      response="$(
        curl "http://127.0.0.1:${forwarding_port}/v1/images/generations" \
          --data "{
            \"model\": \"/gcs/${HF_MODEL_ID}\",
            \"n\": 1,
            \"num_inference_steps\": 4,
            \"output_format\": \"png\",
            \"prompt\": \"A photo of a dog playing fetch in a park.\",
            \"response_format\": \"b64_json\",
            \"size\": \"512x512\"
          }" \
          --fail \
          --header "Content-Type: application/json" \
          --request POST \
          --show-error \
          --silent
      )"
      printf '%s' "${response}" | jq -er '.data[0].b64_json' | base64 --decode >"${output_png}"
    else
      echo "Sending POST request to '/generate' (Diffusers backend)"
      echo "----------------------------------------------------------------------------------"
      curl "http://127.0.0.1:${forwarding_port}/generate" \
        --data '{
          "height": 512,
          "num_inference_steps": 4,
          "prompt": "A photo of a dog playing fetch in a park.",
          "width": 512
        }' \
        --fail \
        --header "Content-Type: application/json" \
        --output "${output_png}" \
        --request POST \
        --show-error \
        --silent
    fi
    sleep 1
    ls -alh "${output_png}"
    png_magic="$(od -An -tx1 -N8 "${output_png}" | tr -d ' \n')"
    if [[ "${png_magic}" != "89504e470d0a1a0a" ]]; then
      echo "[ERROR] Output '${output_png}' is not a valid PNG file (magic=${png_magic})." >&2
      kill -9 "${PF_PID}" 2>/dev/null || true
      wait "${PF_PID}" 2>/dev/null || true
      exit 1
    fi
    echo "----------------------------------------------------------------------------------"
    echo

    kill -9 "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
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
