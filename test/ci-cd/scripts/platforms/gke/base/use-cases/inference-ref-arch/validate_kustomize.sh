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

export HF_MODEL_ID="google/gemma-3-27b-it"

source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"

export ACCELERATOR_TYPE="l4"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/batch-inference-gpu/batch-load-generator/configure_load_generator.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/batch-inference-gpu/batch-pubsub-subscriber/configure_pubsub_subscriber.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/batch-inference-gpu/vllm/configure_vllm.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/configure_diffusers.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/configure_vllm.sh"

export ACCELERATOR_TYPE="v5e"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/configure_max_diffusion.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/configure_vllm.sh"

# Validate inference-perf kustomize 
export ACCELERATOR_TYPE="rtx-pro-6000"
export ACCELERATOR="GPU"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/configure_benchmark.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/configure_vllm_spec_decoding.sh"

find "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/kubernetes-manifests" -name "kustomization.yaml" -print0 | while read -d $'\0' file; do
  kustomize_directory_path="$(dirname "${file}")"
  rendered_kubernetes_manifests_file_path="/tmp/rendered-kustomize.yaml"

  # Basic validation:
  # - Render manifests with Kustomize
  # - Validate manifests with kubectl-validate
  kubectl kustomize "${kustomize_directory_path}" | tee "${rendered_kubernetes_manifests_file_path}"
  kubectl validate "${rendered_kubernetes_manifests_file_path}"
done
