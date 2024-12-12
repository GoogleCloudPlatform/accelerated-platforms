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

TERRAFORM_INIT_COMMAND=(
  terraform init
)

# shellcheck disable=SC2154 # variable defined in common.sh
for terraservice in "${federated_learning_terraservices[@]}"; do
  echo "Provisioning ${terraservice}"
  TERRASERVICE_TERRAFORM_INIT_COMMAND=(
    "${TERRAFORM_INIT_COMMAND[@]}"
  )
  if [ "${terraservice:-}" != "initialize" ]; then
    echo "Add the option to load remote backend configuration to the terraform init command"
    TERRASERVICE_TERRAFORM_INIT_COMMAND+=(
      -backend-config="backend.config"
    )
  fi

  echo "Terraform init command: ${TERRASERVICE_TERRAFORM_INIT_COMMAND[*]}"

  cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    "${TERRASERVICE_TERRAFORM_INIT_COMMAND[@]}" &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan
  rm tfplan
done

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
