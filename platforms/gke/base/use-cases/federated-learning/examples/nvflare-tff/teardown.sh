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

ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../../../")"
export ACP_REPO_DIR
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"
echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"

start_timestamp_federated_learning=$(date +%s)

echo "Stopping NVIDIA FLARE clients"
docker stop nvflare-client1 || true
docker stop nvflare-client2 || true

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
load_fl_terraform_outputs

echo "Destroying the services that the NVIDIA FLARE TFF example depends on"
# shellcheck disable=SC2154 # variable defined in setup-environment.sh
for ((i = ${#nvflare_example_terraservices[@]} - 1; i >= 0; i--)); do
  terraservice=${nvflare_example_terraservices[i]}
  destroy_terraservice "${terraservice}"
done

echo "Removing configuration values from ${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES[@]}"; do
  remove_terraform_configuration_variable_from_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Deleting the generated NVFLARE workspace"
sudo rm -rf "${NVFLARE_GENERATED_WORKSPACE_PATH}"
sudo chown -R "$(id -u)":"$(id -g)" "${NVFLARE_WORKSPACE_PATH}"

echo "Deleting the ${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID} container image from the registry"
gcloud artifacts docker images delete "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID}" \
  --quiet || true

echo "Running the Federated learning use case deploy script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
