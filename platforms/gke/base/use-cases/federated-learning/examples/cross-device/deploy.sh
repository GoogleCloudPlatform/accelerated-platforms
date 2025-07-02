#!/usr/bin/env bash
#
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

# Doesn't follow symlinks, but it's likely expected for most users
SCRIPT_BASENAME="$(basename "${0}")"
SCRIPT_DIRECTORY_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

echo "This script (${SCRIPT_BASENAME}) has been invoked with: $0 $*"
echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../../../")"
export ACP_REPO_DIR
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"
echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/cross-device/setup-environment.sh"

start_timestamp_federated_learning=$(date +%s)

echo "Preparing the reference architecture configuration to deploy the cross-device example"
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case provisioning script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

echo "Refreshing the environment configuration"
load_fl_terraform_outputs

echo "Updating the reference architecture configuration to deploy the cross-device example"
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CROSS_DEVICE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Updating the reference architecture configuration values to deploy the cross-device example"
edit_terraform_configuration_variable_value_in_file "federated_learning_cross_device_apps_service_account_placeholder" "${CROSS_DEVICE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"

echo "Provision services that the cross-device example depends on"
# shellcheck disable=SC2154 # variable defined in setup-environment.sh
for terraservice in "${cross_device_example_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

# shellcheck disable=SC2154 # variable defined in setup-environment.sh
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning cross-device example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"

#!/usr/bin/env bash
#
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

# Doesn't follow symlinks, but it's likely expected for most users
SCRIPT_BASENAME="$(basename "${0}")"
SCRIPT_DIRECTORY_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

echo "This script (${SCRIPT_BASENAME}) has been invoked with: $0 $*"
echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../../../")"
export ACP_REPO_DIR
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"
echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/cross-device/setup-environment.sh"

start_timestamp_federated_learning=$(date +%s)

echo "Preparing the reference architecture configuration to deploy the cross-device example"
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case provisioning script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

echo "Refreshing the environment configuration"
load_fl_terraform_outputs

echo "Updating the reference architecture configuration to deploy the cross-device example"
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CROSS_DEVICE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${CROSS_DEVICE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Updating the reference architecture configuration values to deploy the cross-device example"
edit_terraform_configuration_variable_value_in_file "federated_learning_cross_device_apps_service_account_placeholder" "${CROSS_DEVICE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"

echo "Provision services that the cross-device example depends on"
# shellcheck disable=SC2154 # variable defined in setup-environment.sh
for terraservice in "${cross_device_example_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

# shellcheck disable=SC2154 # variable defined in setup-environment.sh
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning cross-device example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
