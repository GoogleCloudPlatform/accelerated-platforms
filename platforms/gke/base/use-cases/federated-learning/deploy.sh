#!/usr/bin/env bash
#
# Copyright 2024 Google LLC
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

# Doesn't follow symlinks, but it's likely expected for most users
SCRIPT_BASENAME="$(basename "${0}")"
SCRIPT_DIRECTORY_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

echo "This script (${SCRIPT_BASENAME}) has been invoked with: $0 $*"
echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../")"
export ACP_REPO_DIR
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"
echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"

# Enable Terraform plugin caching and specifies location of the plugin cache directory
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

start_timestamp_federated_learning=$(date +%s)

echo "Preparing core platform configuration files"
for configuration_variable in "${TERRAFORM_CLUSTER_CONFIGURATION[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"
done
for configuration_variable in "${TERRAFORM_CORE_INITIALIZE_CONFIGURATION[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${ACP_PLATFORM_SHARED_CONFIG_INITIALIZE_AUTO_VARS_FILE}"
done

echo "Initializing the core platform"
# Don't provision any core platform terraservice because we just need
# to initialize the terraform environment and remote backend
# shellcheck disable=SC1091,SC2154
CORE_TERRASERVICES_APPLY="${core_platform_init_terraservices[*]}" \
  "${ACP_PLATFORM_CORE_DIR}/deploy.sh"

echo "Provision services that the core platform depends on"
# shellcheck disable=SC2154 # variable defined in common.sh
for terraservice in "${federated_learning_core_platform_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

if ! cluster_database_encryption_key_id="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/key_management_service" "cluster_database_encryption_key_id" "raw")"; then
  exit 1
fi
edit_terraform_configuration_variable_value_in_file "cluster_database_encryption_key_name_placeholder" "${cluster_database_encryption_key_id}" "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"

echo "Provisioning the core platform"
# shellcheck disable=SC1091,SC2034,SC2154 # Variable is used in other scripts
CORE_TERRASERVICES_APPLY="${core_platform_terraservices[*]}" \
  "${ACP_PLATFORM_CORE_DIR}/deploy.sh"

echo "Provisioning the use case resources"
# shellcheck disable=SC2154 # variable defined in common.sh
for terraservice in "${federated_learning_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
