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
# shellcheck disable=SC2034 # Variable is used in other scripts
ACP_PLATFORM_SHARED_CONFIG_INITIALIZE_AUTO_VARS_FILE="${ACP_PLATFORM_SHARED_CONFIG_DIR}/initialize.auto.tfvars"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_SHARED_CONFIG_DIR}/scripts/set_environment_variables.sh" "${ACP_PLATFORM_SHARED_CONFIG_DIR}"

FEDERATED_LEARNING_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning"
FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR="${FEDERATED_LEARNING_USE_CASE_DIR}/terraform"
# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_SHARED_CONFIG_DIR="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/_shared_config"

# shellcheck disable=SC2034 # Variable is used in other scripts
# Terraservices that are necessary for the core platform
federated_learning_core_platform_terraservices=(
  "key_management_service"
  "service_account"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
federated_learning_terraservices=(
  "firewall"
  "container_image_repository"
  "private_google_access"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
core_platform_init_terraservices=(
  "initialize"
  "networking"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
core_platform_terraservices=(
  "container_cluster"
  "gke_enterprise/fleet_membership"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
TERRAFORM_CORE_INITIALIZE_CONFIGURATION=(
  "initialize_backend_use_case_name = \"federated-learning\""
)

# shellcheck disable=SC2034 # Variable is used in other scripts
TERRAFORM_CLUSTER_CONFIGURATION=(
  "cluster_binary_authorization_evaluation_mode = \"PROJECT_SINGLETON_POLICY_ENFORCE\""
  "cluster_confidential_nodes_enabled = false"
  "cluster_database_encryption_state = \"ENCRYPTED\""
  "cluster_database_encryption_key_name = \"cluster_database_encryption_key_name_placeholder\""
)

apply_or_destroy_terraservice() {
  local terraservice
  terraservice="${1}"

  local operation_mode
  operation_mode="${2:-"not set"}"

  echo "Initializing ${terraservice} Terraform environment"
  cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" &&
    terraform init

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

  if [[ ! -d "${terraservice}" ]]; then
    echo "${terraservice} directory doesn't exist or is not readable"
    return 1
  fi

  local output
  if ! output="$(terraform -chdir="${terraservice}" init)"; then
    echo "Error while initializing ${terraservice} to get ${output_name} output: ${output}"
    return 1
  fi

  if ! output="$(
    terraform -chdir="${terraservice}" output -raw "${output_name}"
  )"; then
    echo "Error while getting ${output_name} output: ${output}"
    return 1
  fi
  echo "${output}"
}

write_terraform_configuration_variable_to_file() {
  local configuration_variable="${1}"
  local destination_file_path="${2}"
  local configuration_variable_name

  configuration_variable_name="$(echo "${configuration_variable}" | awk '{ print $1 }')"
  echo "Checking if ${configuration_variable_name} is in ${destination_file_path}"
  grep -q "${configuration_variable_name}" "${destination_file_path}" || echo "${configuration_variable}" >>"${destination_file_path}"
  terraform fmt "${destination_file_path}"
}

remove_terraform_configuration_variable_from_file() {
  local configuration_variable="${1}"
  local destination_file_path="${2}"
  local configuration_variable_name

  configuration_variable_name="$(echo "${configuration_variable}" | awk ' { print $1 }'))"
  sed -i "/${configuration_variable_name}/d" "${destination_file_path}"
  terraform fmt "${destination_file_path}"
}

edit_terraform_configuration_variable_value_in_file() {
  local configuration_variable_placeholder_value="${1}"
  local configuration_variable_value="${2}"
  local destination_file_path="${3}"

  echo "Changing the value of ${configuration_variable_placeholder_value} to ${configuration_variable_value} in ${destination_file_path}"

  # Use | as a separator in the sed command because substitution values might contain slashes
  local sed_command="s|${configuration_variable_placeholder_value}|${configuration_variable_value}|g"
  echo "sed command: ${sed_command}"
  sed -i "${sed_command}" "${destination_file_path}"
  terraform fmt "${destination_file_path}"
}
