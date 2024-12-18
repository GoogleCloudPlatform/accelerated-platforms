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

ACP_PLATFORM_SHARED_CONFIG_DIR="${ACP_PLATFORM_BASE_DIR}/_shared_config"

# shellcheck disable=SC2034 # Variable is used in other scripts
ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE="${ACP_PLATFORM_SHARED_CONFIG_DIR}/cluster.auto.tfvars"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_SHARED_CONFIG_DIR}/scripts/set_environment_variables.sh" "${ACP_PLATFORM_SHARED_CONFIG_DIR}"

FEDERATED_LEARNING_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning"
FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR="${FEDERATED_LEARNING_USE_CASE_DIR}/terraform"
# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_SHARED_CONFIG_DIR="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/_shared_config"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_USE_CASE_INITIALIZE_SERVICE_DIR="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/initialize"

# Terraservices that are necessary for the core platform
federated_learning_core_platform_terraservices=(
  "initialize"
  "key_management_service"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
federated_learning_terraservices=(
  "${federated_learning_core_platform_terraservices[@]}"
  "container_image_repository"
  "private_google_access"
)

TERRAFORM_INIT_COMMAND=(
  terraform init
)

# shellcheck disable=SC2034 # Variable is used in other scripts
TERRAFORM_INIT_BACKEND_CONFIG_COMMAND=(
  "${TERRAFORM_INIT_COMMAND[@]}"
  -backend-config="backend.config"
)

# The values of some variables depends on Terraform outputs
# shellcheck disable=SC2034 # Variable is used in other scripts
TERRAFORM_CLUSTER_CONFIGURATION=(
  "cluster_binary_authorization_evaluation_mode = \"PROJECT_SINGLETON_POLICY_ENFORCE\""
  "cluster_confidential_nodes_enabled = false"
  "cluster_database_encryption_state = \"ENCRYPTED\""
  "cluster_database_encryption_key_name = \"cluster_database_encryption_key_name_placeholder\""
)

provision_terraservice() {
  local terraservice
  terraservice="${1}"

  local -a TERRASERVICE_TERRAFORM_INIT_COMMAND

  echo "Provisioning ${terraservice}"
  TERRASERVICE_TERRAFORM_INIT_COMMAND=(
    "${TERRAFORM_INIT_BACKEND_CONFIG_COMMAND[@]}"
  )

  if [ "${terraservice:-}" == "initialize" ]; then
    TERRASERVICE_TERRAFORM_INIT_COMMAND=(
      "${TERRAFORM_INIT_COMMAND[@]}"
    )
  fi

  echo "Terraform init command for ${terraservice}: ${TERRASERVICE_TERRAFORM_INIT_COMMAND[*]}"

  cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    "${TERRASERVICE_TERRAFORM_INIT_COMMAND[@]}" &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan
  local _apply_result=$?
  rm tfplan
  if [[ ${_apply_result} -ne 0 ]]; then
    echo "Terraform apply for ${terraservice} failed with code ${_apply_result}"
    exit $_apply_result
  fi
}

get_terraform_output() {
  terraservice="${1}"
  output_name="${2}"
  local output
  if ! output="$(cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" && terraform output -raw "${output_name}")"; then
    echo "Error while getting ${output_name} output"
    return 1
  fi
  echo "${output}"
}
