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

MY_PATH="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd -P)"
export ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../")"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/agent-substrate-secure-runtime"
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
export PATH="${HOME}/google-cloud-sdk/bin:${PATH}"

export TF_VAR_initialize_backend_use_case_name="agent-substrate-secure-runtime/terraform"
export TF_VAR_initialize_container_node_pools_cpu="true"
export TF_VAR_initialize_container_node_pools_gpu="false"
export TF_VAR_initialize_container_node_pools_tpu="false"
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-sec}"

if [ "${ACP_DEPLOY_CORE_PLATFORM:-true}" = "true" ]; then
  "${ACP_PLATFORM_CORE_DIR}/deploy-standard.sh"
  CORE_TERRASERVICES_APPLY="container_node_pool cloudbuild/initialize workloads/agent_substrate" \
    "${ACP_PLATFORM_CORE_DIR}/deploy.sh"
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/secure_runtime"
rm -rf .terraform/
terraform init
terraform apply -input=false -auto-approve

# shellcheck disable=SC2154
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint
