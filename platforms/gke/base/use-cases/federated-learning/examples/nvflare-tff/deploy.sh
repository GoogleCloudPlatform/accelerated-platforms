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

echo "Preparing the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case provisioning script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

echo "Updating the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Refreshing the environment configuration before applying changes because we updated the reference architecture configuration"
load_fl_terraform_outputs

echo "Updating the reference architecture configuration values to deploy the NVIDIA FLARE TFF example"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_apps_service_account_placeholder" "${NVFLARE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_bucket_name_placeholder" "${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_TAG}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"

echo "Running the Federated learning use case provisioning script again because we updated the reference architecture configuration"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
