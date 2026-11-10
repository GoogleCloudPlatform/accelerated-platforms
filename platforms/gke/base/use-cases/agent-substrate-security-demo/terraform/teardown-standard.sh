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
mkdir -p "${TF_PLUGIN_CACHE_DIR}"

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="agent-substrate-security-demo/terraform"
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-ate}"

# Set execution specific values
export ACP_TEARDOWN_CORE_PLATFORM=${ACP_TEARDOWN_CORE_PLATFORM:-"true"}

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/scripts/port-forward.sh"
stop_managed_port_forwards "${ACP_PLATFORM_USE_CASE_DIR}/.state"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

# Remove cluster-scoped Cloud Monitoring dashboards created during stage.sh
# shellcheck disable=SC2154
PROJECT_ID="${cluster_project_id}" \
CLUSTER_NAME="${cluster_name}" \
  "${ACP_PLATFORM_USE_CASE_DIR}/scripts/dashboards.sh" delete || true

# Release dynamically provisioned 500Gi Postgres PVC before destroying the cluster
# shellcheck disable=SC2154
if gcloud container clusters describe "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" >/dev/null 2>&1; then
  gcloud container clusters get-credentials "${cluster_name}" \
    --region "${cluster_region}" \
    --project "${cluster_project_id}" \
    --dns-endpoint >/dev/null 2>&1 || true
  kubectl -n ate-system delete statefulset postgres --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n ate-system delete pvc --all --ignore-not-found --timeout=60s >/dev/null 2>&1 || true
fi

# shellcheck disable=SC2154
cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
  echo "Current directory: $(pwd)" &&
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" &&
  cp backend.tf.bucket backend.tf &&
  rm -rf .terraform/ &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

declare -a use_case_terraservices=(
  "agent_substrate_security_demo"
  "initialize"
)
for terraservice in "${use_case_terraservices[@]}"; do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform destroy -auto-approve || exit 1
  rm -rf .terraform/ \
    "terraform.tfstate"*
done

rm -rf \
  "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/.terraform/" \
  "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/terraform.tfstate"* \
  "${ACP_PLATFORM_USE_CASE_DIR}/.state"

if [ "${ACP_TEARDOWN_CORE_PLATFORM}" = "true" ]; then
  "${ACP_PLATFORM_CORE_DIR}/teardown-standard.sh"
else
  echo "Skipping core platform teardown."
fi

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
printf 'agent-substrate-security-demo teardown total runtime: %02d:%02d:%02d\n' \
  "$((total_runtime_value / 3600))" \
  "$((total_runtime_value % 3600 / 60))" \
  "$((total_runtime_value % 60))"
