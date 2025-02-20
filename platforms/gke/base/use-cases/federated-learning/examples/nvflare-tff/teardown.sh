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

start_timestamp_federated_learning=$(date +%s)

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"

echo "Removing configuration values from ${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case deploy script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
