#!/usr/bin/env bash

# Copyright 2025 Google LLC
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
set -o errexit
set -o nounset
set -o pipefail

source /workspace/build.env
if [ "${DEBUG,,}" == "true" ]; then
  set -o xtrace
fi

STEP_ID=${1}

exit_handler() {
  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "${STEP_ID}" >>/workspace/build-failed.lock
  fi

  exit 0
}
trap exit_handler EXIT

set --
source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

envsubst <"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/templates/secretproviderclass-huggingface-tokens.tpl.yaml" |
  sponge "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/secretproviderclass-huggingface-tokens.yaml"

export MODEL_ID="google/gemma-3-27b-it"

envsubst <"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/templates/downloader.tpl.env" |
  sponge "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/downloader.env"

export MODEL_NAME="gemma3-27b"
export ACCELERATOR_TYPE="l4"

envsubst <"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-base/templates/deployment.tpl.env" |
  sponge "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-base/deployment.env"

find "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/kubernetes-manifests" -name "kustomization.yaml" -print0 | while read -d $'\0' file; do
  kustomize_directory_path="$(dirname "${file}")"
  rendered_kubernetes_manifests_file_path="/tmp/rendered-kustomize.yaml"

  # Basic validation:
  # - Render manifests with Kustomize
  # - Validate manifests with kubectl-validate
  kubectl kustomize "${kustomize_directory_path}" | tee "${rendered_kubernetes_manifests_file_path}"
  kubectl validate "${rendered_kubernetes_manifests_file_path}"
done
