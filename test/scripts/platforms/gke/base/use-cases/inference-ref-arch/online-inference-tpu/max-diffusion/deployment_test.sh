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
  models=("${hf_tpu_max_diffusion_models[@]}")
fi

for model in "${models[@]}"; do
  export HF_MODEL_ID="${model}"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  overlay_dir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  if [[ -d "${overlay_dir}" ]]; then
    echo "Testing '${HF_MODEL_ID}' model deployment on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"

    echo "Setting up port forwarding..."
    forwarding_port="$(shuf -i 49152-65535 -n 1)"
    kubectl --namespace="${ira_online_tpu_kubernetes_namespace_name}" port-forward --address 127.0.0.1 "service/max-diffusion-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" "${forwarding_port}:8000" >/dev/null &
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

    output_png="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png"
    mkdir -p "$(dirname "${output_png}")"
    rm -f "${output_png}"

    echo "Sending POST request to '/generate'"
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
    ls -alh "${output_png}"
    png_magic="$(od -An -tx1 -N8 "${output_png}" | tr -d ' \n')"
    if [[ "${png_magic}" != "89504e470d0a1a0a" ]]; then
      echo "[ERROR] Output '${output_png}' is not a valid PNG file (magic=${png_magic})." >&2
      exit 1
    fi
    echo "----------------------------------------------------------------------------------"
    echo

    cleanup_port_forward
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
