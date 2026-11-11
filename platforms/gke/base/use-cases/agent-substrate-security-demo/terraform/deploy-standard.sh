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
mkdir -p "${TF_PLUGIN_CACHE_DIR}"

# Set execution specific values
export ACP_DEPLOY_CORE_PLATFORM=${ACP_DEPLOY_CORE_PLATFORM:-"true"}
export ACP_STAGE_DEMO=${ACP_STAGE_DEMO:-"true"}

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="agent-substrate-security-demo/terraform"
if [ "${ACP_DEPLOY_CORE_PLATFORM}" = "true" ]; then
  export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-ate}"
elif ! grep -q '^resource_name_prefix' "${ACP_PLATFORM_BASE_DIR}/_shared_config/platform.auto.tfvars" 2>/dev/null; then
  export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-acp}"
fi

if [ "${ACP_DEPLOY_CORE_PLATFORM}" = "true" ]; then
  "${ACP_PLATFORM_CORE_DIR}/deploy-standard.sh"
else
  echo "Skipping core platform deployment; initializing use-case Terraform backend."
  # shellcheck disable=SC1091
  source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"
  # shellcheck disable=SC2154
  cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
    sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" &&
    initialize_state_prefix="$(sed -n 's/^[[:blank:]]*prefix[[:blank:]]*=[[:blank:]]*"\(.*\)"[[:blank:]]*$/\1/p' "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket")" &&
    if gcloud storage ls "gs://${terraform_bucket_name}/${initialize_state_prefix}/default.tfstate" &>/dev/null; then
      cp backend.tf.bucket backend.tf
      STATE_MIGRATED="true"
    else
      rm -f backend.tf
      STATE_MIGRATED="false"
    fi &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm -f tfplan
  if [ "${STATE_MIGRATED}" = "false" ]; then
    terraform init -force-copy -migrate-state || exit 1
    rm -rf terraform.tfstate*
  fi
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

declare -a use_case_terraservices=(
  "agent_substrate_security_demo"
)
for terraservice in "${use_case_terraservices[@]}"; do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm -f tfplan
done

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

if [ "${UPDATE_KUBECONFIG:-true}" = "true" ]; then
  # shellcheck disable=SC2154
  echo "Updating kubeconfig context for cluster '${cluster_name}' (${cluster_region})..."
  gcloud container clusters get-credentials "${cluster_name}" \
    --region "${cluster_region}" \
    --project "${cluster_project_id}" \
    --dns-endpoint
fi

if [ "${ACP_STAGE_DEMO}" = "true" ]; then
  # shellcheck disable=SC2154
  PROVISION_GCP_INFRA="false" \
  PROJECT_ID="${agent_substrate_project_id}" \
  CLUSTER_NAME="${cluster_name}" \
  CLUSTER_LOCATION="${cluster_region}" \
  AR_REPO="${agent_substrate_ar_repository_name}" \
  BUCKET_NAME="${agent_substrate_snapshot_bucket_name}" \
  SNAPSHOT_TRANSFER_GSA_NAME="${agent_substrate_snapshot_transfer_gsa_name}" \
  NAMESPACE="${agent_substrate_workload_namespace}" \
  SECRETS_NAMESPACE="${agent_substrate_secrets_namespace}" \
  ATESPACE="${agent_substrate_atespace_name}" \
  MIN_GKE_VERSION="${agent_substrate_min_gke_version}" \
  SUBSTRATE_REF="${agent_substrate_version}" \
    "${ACP_PLATFORM_USE_CASE_DIR}/scripts/stage.sh"
fi

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
printf 'agent-substrate-security-demo deploy total runtime: %02d:%02d:%02d\n' \
  "$((total_runtime_value / 3600))" \
  "$((total_runtime_value % 3600 / 60))" \
  "$((total_runtime_value % 60))"
