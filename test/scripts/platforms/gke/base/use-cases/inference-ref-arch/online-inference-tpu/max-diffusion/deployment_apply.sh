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

for model in "${hf_tpu_max_diffusion_models[@]}"; do
  export HF_MODEL_ID=${model}
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  if [[ -d "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}" ]]; then
    echo "Deploying '${HF_MODEL_ID}' model resources on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/configure_max_diffusion.sh"
    kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
    echo
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
