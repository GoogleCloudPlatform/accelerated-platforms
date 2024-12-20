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

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

start_timestamp_federated_learning=$(date +%s)

echo "Preparing core platform configuration files"
for configuration_variable in "${TERRAFORM_CLUSTER_CONFIGURATION[@]}"; do
  configuration_variable_name="$(echo "${configuration_variable}" | awk '{ print $1 }')"
  echo "Checking if ${configuration_variable_name} is in ${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"
  grep -q "${configuration_variable_name}" "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}" || echo "${configuration_variable}" >>"${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"
done
terraform fmt "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"

echo "Provisioning the core platform"
"${ACP_PLATFORM_CORE_DIR}/deploy.sh"

echo "Provisioning the use case resources"
# shellcheck disable=SC2154 # variable defined in common.sh
for terraservice in "${federated_learning_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
