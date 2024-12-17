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

# shellcheck disable=SC2034 # Variable is used in other scripts
federated_learning_terraservices=(
  "initialize"
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

# shellcheck disable=SC2034 # Variable is used in other scripts
TERRAFORM_CLUSTER_CONFIGURATION=(
)

apply_or_destroy_terraservice() {
  local terraservice
  terraservice="${1}"

  local operation_mode
  operation_mode="${2:-"not set"}"

  local -a TERRASERVICE_TERRAFORM_INIT_COMMAND
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
    "${TERRASERVICE_TERRAFORM_INIT_COMMAND[@]}"

  echo "Current working directory: $(pwd)"

  if [[ "${operation_mode}" == "apply" ]]; then
    echo "Provisioning ${terraservice}"
    terraform plan -input=false -out=tfplan &&
      terraform apply -input=false tfplan
    _terraform_result=$?
  elif [[ "${operation_mode}" == "destroy" ]]; then
    echo "Destroying ${terraservice}"
    terraform destroy -auto-approve
    _terraform_result=$?
  else
    echo "Error: operation mode not supported: ${operation_mode}"
    _terraform_result=1
  fi

  rm -rf \
    "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}/.terraform" \
    "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}/tfplan"

  if [[ ${_terraform_result} -ne 0 ]]; then
    echo "Terraform ${operation_mode} command failed with code ${_terraform_result} for ${terraservice}"
    exit ${_terraform_result}
  fi
}

provision_terraservice() {
  apply_or_destroy_terraservice "${1}" "apply"
}

destroy_terraservice() {
  apply_or_destroy_terraservice "${1}" "destroy"
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
