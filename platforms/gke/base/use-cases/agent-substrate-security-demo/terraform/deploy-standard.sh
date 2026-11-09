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
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/agent-substrate-security-demo"

# Enable Terraform plugin caching
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="agent-substrate-security-demo/terraform"
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-ate}"
export TF_VAR_cluster_release_channel="${TF_VAR_cluster_release_channel:-RAPID}"
export TF_VAR_cluster_min_master_version="${TF_VAR_cluster_min_master_version:-1.37}"
export TF_VAR_cluster_addons_agent_sandbox_enabled="${TF_VAR_cluster_addons_agent_sandbox_enabled:-true}"

# Set execution specific values
export ACP_DEPLOY_CORE_PLATFORM=${ACP_DEPLOY_CORE_PLATFORM:-"true"}
export ACP_STAGE_DEMO=${ACP_STAGE_DEMO:-"true"}

if [ "${ACP_DEPLOY_CORE_PLATFORM}" = "true" ]; then
  "${ACP_PLATFORM_CORE_DIR}/deploy-standard.sh"

  declare -a CORE_TERRASERVICES_APPLY=(
    "cloudbuild/initialize"
    "workloads/agent_sandbox"
  )
  CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY[*]}" "${ACP_PLATFORM_CORE_DIR}/deploy.sh"
else
  echo "Skipping core platform deployment."
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

declare -a use_case_terraservices=(
  "initialize"
  "agent_substrate_security_demo"
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

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

# shellcheck disable=SC2154
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

if [ "${ACP_STAGE_DEMO}" = "true" ]; then
  # shellcheck disable=SC2154
  PROJECT_ID="${cluster_project_id}" \
  CLUSTER_NAME="${cluster_name}" \
  CLUSTER_LOCATION="${cluster_region}" \
  BUCKET_NAME="${agent_substrate_snapshot_bucket_name}" \
  ATESPACE="${agent_substrate_atespace_name}" \
  SUBSTRATE_REF="${agent_substrate_version}" \
    "${ACP_PLATFORM_USE_CASE_DIR}/scripts/stage.sh"
fi

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
printf 'agent-substrate-security-demo deploy total runtime: %02d:%02d:%02d\n' \
  "$((total_runtime_value / 3600))" \
  "$((total_runtime_value % 3600 / 60))" \
  "$((total_runtime_value % 60))"
