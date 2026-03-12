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

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
MY_NAME=$(basename "${0}" .sh)

declare -A start_timestamp["${MY_NAME}"]
start_timestamp["${MY_NAME}"]=$(date +%s)

# Set repository values
export ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../..)"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/training-ref-arch"

# Enable Terraform plugin caching and specifies location of the plugin cache directory
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="training-ref-arch/terraform"
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-trn}"

declare -a CORE_TERRASERVICES_APPLY=(
  "networking"
  "container_cluster"
  "workloads/cluster_credentials"
  "custom_compute_class"
  "workloads/kueue"
  "cloudbuild/initialize"
  "huggingface/initialize"
  "kaggle/initialize"
)
CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY[*]}" "${ACP_PLATFORM_CORE_DIR}/deploy.sh"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

declare -a use_case_terraservices=(
  "initialize"
)
for terraservice in "${use_case_terraservices[@]}"; do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm tfplan
done

${cluster_credentials_command}

declare -A end_timestamp["${MY_NAME}"]
end_timestamp["${MY_NAME}"]=$(date +%s)
total_runtime_value=$((end_timestamp["${MY_NAME}"] - start_timestamp["${MY_NAME}"]))
echo
echo "Total runtime (${MY_NAME}): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
