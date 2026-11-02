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

start_timestamp=$(date +%s)

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# Set repository values
export ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../")"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/agent-substrate-secure-runtime"

# Enable Terraform plugin caching and specify location of the plugin cache directory
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

if [ -d "${HOME}/google-cloud-sdk/bin" ]; then
  export PATH="${HOME}/google-cloud-sdk/bin:${PATH}"
fi

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="agent-substrate-secure-runtime/terraform"
export TF_VAR_initialize_container_node_pools_cpu="true"
export TF_VAR_initialize_container_node_pools_gpu="false"
export TF_VAR_initialize_container_node_pools_tpu="false"
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-sec}"

# Set execution specific values
export ACP_DEPLOY_CORE_PLATFORM=${ACP_DEPLOY_CORE_PLATFORM:-"true"}

if [ "${ACP_DEPLOY_CORE_PLATFORM}" = "true" ]; then
  # Deploy GKE Base Reference Architecture core platform with standard services
  "${ACP_PLATFORM_CORE_DIR}/deploy-standard.sh"

  # Deploy additional core services required by Agent Substrate & Secure Runtime:
  # - container_node_pool: provisions the uniform c3-standard-4 worker pool & gVisor baseline pool
  # - cloudbuild/initialize: provisions Artifact Registry & Cloud Build service account
  # - workloads/agent_substrate: installs Agent Substrate control plane + GCS snapshot bucket
  declare -a CORE_TERRASERVICES_APPLY=(
    "container_node_pool"
    "cloudbuild/initialize"
    "workloads/agent_substrate"
  )
  CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY[*]}" "${ACP_PLATFORM_CORE_DIR}/deploy.sh"
else
  echo "Skipping core platform deployment."
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

declare -a use_case_terraservices=(
  "initialize"
  "secure_runtime"
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

# shellcheck disable=SC2154
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "agent-substrate-secure-runtime deploy total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
