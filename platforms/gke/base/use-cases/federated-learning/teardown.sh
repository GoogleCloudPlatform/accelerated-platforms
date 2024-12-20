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

# Iterate over the terraservices array so we destroy them in reverse order, keeping the
# initialize terraservice last.
# shellcheck disable=SC2154 # variable defined in common.sh
for ((i = ${#federated_learning_terraservices[@]} - 1; i >= 0; i--)); do
  terraservice=${federated_learning_terraservices[i]}
  destroy_terraservice "${terraservice}"
done

echo "Destroying the core platform"
"${ACP_PLATFORM_CORE_DIR}/teardown.sh"

for configuration_variable in "${TERRAFORM_CLUSTER_CONFIGURATION[@]}"; do
  configuration_variable_name="$(echo "${configuration_variable}" | awk ' { print $1 }'))"
  sed -i "/${configuration_variable_name}/d" "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"
done
terraform fmt "${ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE}"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
