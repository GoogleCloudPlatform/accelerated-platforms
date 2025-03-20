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

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

start_timestamp_federated_learning=$(date +%s)

echo "Destroy the use case terraservices"
# Iterate over the terraservices array so we destroy them in reverse order
# shellcheck disable=SC2154 # variable defined in common.sh
for ((i = ${#federated_learning_terraservices[@]} - 1; i >= 0; i--)); do
  terraservice=${federated_learning_terraservices[i]}
  destroy_terraservice "${terraservice}"
done

echo "Destroying the core platform"
CORE_TERRASERVICES_DESTROY=""
# shellcheck disable=SC2154 # variable defined in common.sh
for ((i = ${#core_platform_terraservices[@]} - 1; i >= 0; i--)); do
  CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY} ${core_platform_terraservices[i]}"
done
# Trim leading space
CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY#"${CORE_TERRASERVICES_DESTROY%%[![:space:]]*}"}"
CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY}" \
  "${ACP_PLATFORM_CORE_DIR}/teardown.sh"

echo "Destroying the services that the core platform depends on"
# shellcheck disable=SC2154 # variable defined in common.sh
for ((i = ${#federated_learning_core_platform_terraservices[@]} - 1; i >= 0; i--)); do
  terraservice=${federated_learning_core_platform_terraservices[i]}
  destroy_terraservice "${terraservice}"
done

echo "Destroying the initialization core platform services"
CORE_TERRASERVICES_DESTROY=""
# shellcheck disable=SC2154 # variable defined in common.sh
for ((i = ${#core_platform_init_terraservices[@]} - 1; i >= 0; i--)); do
  CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY} ${core_platform_init_terraservices[i]}"
done
# Trim leading space
CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY#"${CORE_TERRASERVICES_DESTROY%%[![:space:]]*}"}"
CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY}" \
  "${ACP_PLATFORM_CORE_DIR}/teardown.sh"

for configuration_variable in "${TERRAFORM_CLUSTER_CONFIGURATION[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"
done
for configuration_variable in "${TERRAFORM_CORE_INITIALIZE_CONFIGURATION[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${ACP_PLATFORM_SHARED_CONFIG_INITIALIZE_AUTO_VARS_FILE}"
done

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
