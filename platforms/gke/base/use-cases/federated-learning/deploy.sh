#!/usr/bin/env sh
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

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config

FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR="${FEDERATED_LEARNING_USE_CASE_DIR}/terraform"

terraform -chdir="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" init
terraform -chdir="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" plan -input=false -out=tfplan
terraform -chdir="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" apply -input=false tfplan

rm "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/tfplan"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
