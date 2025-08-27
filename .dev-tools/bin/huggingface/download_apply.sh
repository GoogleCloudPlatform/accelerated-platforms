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

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../)"

source "${MY_PATH}/../helpers/hf.sh"

source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

for model in "${hf_gpu_models[@]}"; do
  export HF_MODEL_ID=${model}
  echo "Deploying '${HF_MODEL_ID}' download resources..."
  echo "--------------------------------------------------------------------------------------------"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  echo
done
