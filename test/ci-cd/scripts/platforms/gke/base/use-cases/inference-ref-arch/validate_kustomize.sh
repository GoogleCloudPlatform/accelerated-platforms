#!/usr/bin/env bash

# Copyright 2026 Google LLC
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

INFO="\033[1;34m[INFO]\033[0m"

echo -e "${INFO} Running validate_kustomize.sh from CI-CD scripts..."

# We need to source build.env to get all the exported variables from the pre-requisite scripts
# This script is called from the CI/CD pipeline which creates the /workspace/build.env file
source /workspace/build.env
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export CONFIG_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm"


# Validate online-inference-gpu/vllm-runai kustomize
export ACCELERATOR_TYPE="l4"
export HF_MODEL_ID="google/gemma-3-27b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm.sh"

export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="google/gemma-4-31b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm.sh"


# Validate online-inference-gpu/vllm-standard kustomize
export ACCELERATOR_TYPE="l4"
export HF_MODEL_ID="google/gemma-3-27b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-standard/configure_vllm.sh"

export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="google/gemma-4-31b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-standard/configure_vllm.sh"

# Validate online-inference-gpu/vllm-tpu kustomize
export ACCELERATOR_TYPE="v6e"
export HF_MODEL_ID="google/gemma-4-31b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-tpu/configure_vllm.sh"


# Validate online-inference-gpu/vllm-spec-decoding kustomize
export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="google/gemma-4-31b-it"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/configure_vllm_spec_decoding.sh"

# Validate k6-benchmark kustomize
export ACCELERATOR_TYPE="l4"
export HF_MODEL_NAME="HF_MODEL_NAME"
export K6_REQUEST_BATCH_SIZE=1
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark/configure_deployment.sh"

# Validate offline-batch-inference-gpu kustomize
export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="meta-llama/Llama-3.3-70B-Instruct"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/configure_jobset.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-dataset-downloader/configure_dataset_downloader.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-worker/configure_worker.sh"

# This section deals with validating kustomize for llm deployment. It is slightly different because it exists `examples` directory and not under the `terraform`directory.
# HF_MODEL_ID and ACCELERATOR_TYPE for llmd deployment are derived from llm_model_id and llm_accelerator_type variables respectively when the env variable file is sourced.
# If we do not set llm_model_id and llm_accelerator_type below, HF_MODEL_ID and ACCELERATOR_TYPE will be set to the default values of these variables respectively.
export llmd_model_id="google/gemma-3-27b-it"
export llmd_accelerator_type="l4"
source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd/vllm/configure_vllm.sh"

# Validate vllm-native-cache-offloading kustomize
export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="qwen/qwen3-32b"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/configure_vllm.sh"

# kubectl validate requires local copies of CustomResourceDefinitions (CRDs)
# to successfully validate manifests that use them (e.g. ServiceMonitors), since
# the CI environment does not have access to a live cluster to query the schemas.
CRD_DIR="${ACP_REPO_DIR}/test/ci-cd/crds"
LOCAL_CRDS_FLAG=""
if [ -d "${CRD_DIR}" ]; then
  LOCAL_CRDS_FLAG="--local-crds ${CRD_DIR}"
fi

find "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/kubernetes-manifests" -name "kustomization.yaml" -print0 | while read -d $'\0' file; do
  kustomize_directory_path="$(dirname "${file}")"
  rendered_kubernetes_manifests_file_path="/tmp/rendered-kustomize.yaml"

  # Basic validation:
  # - Render manifests with Kustomize
  # - Validate manifests with kubectl-validate using local CRDs
  kubectl kustomize "${kustomize_directory_path}" | tee "${rendered_kubernetes_manifests_file_path}"
  kubectl validate ${LOCAL_CRDS_FLAG} "${rendered_kubernetes_manifests_file_path}"
done
