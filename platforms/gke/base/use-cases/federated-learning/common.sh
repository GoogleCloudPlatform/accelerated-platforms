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

# Don't set errexit because we might source this script from an interactive
# shell, and we don't want to exit the shell on errors
# set -o errexit
set -o nounset
set -o pipefail

# Ignoring SC2034 because this variable is used in other scripts
# shellcheck disable=SC2034
EXIT_OK=0
# shellcheck disable=SC2034
EXIT_GENERIC_ERR=1
# shellcheck disable=SC2034
ERR_ARGUMENT_EVAL_ERROR=2
# shellcheck disable=SC2034
ERR_MISSING_DEPENDENCY=3

# shellcheck disable=SC2034
HELP_DESCRIPTION="show this help message and exit"

ACP_PLATFORM_SHARED_CONFIG_DIR="${ACP_PLATFORM_BASE_DIR}/_shared_config"

# shellcheck disable=SC2034 # Variable is used in other scripts
ACP_PLATFORM_SHARED_CONFIG_CLUSTER_AUTO_VARS_FILE="${ACP_PLATFORM_SHARED_CONFIG_DIR}/cluster.auto.tfvars"
# shellcheck disable=SC2034 # Variable is used in other scripts
ACP_PLATFORM_SHARED_CONFIG_INITIALIZE_AUTO_VARS_FILE="${ACP_PLATFORM_SHARED_CONFIG_DIR}/initialize.auto.tfvars"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_SHARED_CONFIG_DIR}/scripts/set_environment_variables.sh" "${ACP_PLATFORM_SHARED_CONFIG_DIR}"
# shellcheck disable=SC1091
source "${ACP_PLATFORM_CORE_DIR}/functions.sh"

FEDERATED_LEARNING_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning"
FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR="${FEDERATED_LEARNING_USE_CASE_DIR}/terraform"
# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_SHARED_CONFIG_DIR="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/_shared_config"
# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE="${FEDERATED_LEARNING_SHARED_CONFIG_DIR}/uc_federated_learning.auto.tfvars"

# shellcheck disable=SC2034 # Variable is used in other scripts
# Terraservices that are necessary for the core platform
federated_learning_core_platform_terraservices=(
  "key_management_service"
  "service_account"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
federated_learning_terraservices=(
  "initialize"
  "firewall"
  "container_image_repository"
  "private_google_access"
  "container_node_pool"
  "config_management"
  "cloud_storage"
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
  "gke_enterprise/configmanagement/oci"
  "gke_enterprise/policycontroller"
  "gke_enterprise/servicemesh"
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

check_exec_dependency() {
  local EXECUTABLE_NAME="${1}"

  if ! command -v "${EXECUTABLE_NAME}" >/dev/null 2>&1; then
    echo "[ERROR]: ${EXECUTABLE_NAME} command is not available, but it's needed. Make it available in PATH and try again. Terminating..."
    exit "${ERR_MISSING_DEPENDENCY}"
  else
    echo "[OK]: ${EXECUTABLE_NAME} is available in PATH, pointing to: $(command -v "${EXECUTABLE_NAME}")"
  fi
}

echo "Checking if the necessary dependencies are available..."
check_exec_dependency "getopt"
check_exec_dependency "grep"
check_exec_dependency "terraform"

is_linux() {
  local OS_RELEASE_INFORMATION_FILE_PATH="/etc/os-release"
  if [ -e "${OS_RELEASE_INFORMATION_FILE_PATH}" ]; then
    return 0
  elif check_exec_dependency "uname"; then
    local os_name
    os_name="$(uname -s)"
    if [ "${os_name#*"Linux"}" != "$os_name" ]; then
      return "${EXIT_OK}"
    else
      return "${EXIT_GENERIC_ERR}"
    fi
  else
    echo "Unable to determine if the OS is Linux."
    return ${EXIT_GENERIC_ERR}
  fi
}

is_macos() {
  local os_name
  os_name="$(uname -s)"
  if [ "${os_name#*"Darwin"}" != "$os_name" ]; then
    return "${EXIT_OK}"
  else
    return "${EXIT_GENERIC_ERR}"
  fi
}

check_argument() {
  local ARGUMENT_VALUE="${1}"
  local ARGUMENT_DESCRIPTION="${2}"

  if [ -z "${ARGUMENT_VALUE}" ]; then
    echo "[ERROR]: ${ARGUMENT_DESCRIPTION} is not defined. Run this command with the -h option to get help. Terminating..."
    exit "${ERR_ARGUMENT_EVAL_ERROR}"
  else
    echo "[OK]: ${ARGUMENT_DESCRIPTION} value is defined: ${ARGUMENT_VALUE}"
  fi
}

check_optional_argument() {
  local ARGUMENT_VALUE="${1}"
  shift
  local ARGUMENT_DESCRIPTION="${1}"
  shift
  local VALUE_NOT_DEFINED_MESSAGE="$*"

  if [ -z "${ARGUMENT_VALUE}" ]; then
    echo "[OK]: optional ${ARGUMENT_DESCRIPTION} is not defined."
    RET_CODE=1
    if [ -n "${VALUE_NOT_DEFINED_MESSAGE}" ]; then
      echo "${VALUE_NOT_DEFINED_MESSAGE}"
    fi
  else
    echo "[OK]: optional ${ARGUMENT_DESCRIPTION} value is defined: ${ARGUMENT_VALUE}"
    RET_CODE=0
  fi

  return "${RET_CODE}"
}

apply_or_destroy_terraservice() {
  local terraservice
  terraservice="${1}"

  local operation_mode
  operation_mode="${2:-"not set"}"

  echo "Initializing ${terraservice} Terraform environment"
  cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" &&
    terraform init -input=false

  echo "Current working directory: $(pwd)"

  if [[ "${operation_mode}" == "apply" ]]; then
    echo "Provisioning ${terraservice}"
    terraform plan -input=false -out=tfplan &&
      terraform apply -input=false tfplan
    _terraform_result=$?
  elif [[ "${operation_mode}" == "destroy" ]]; then
    echo "Destroying ${terraservice}"
    terraform destroy \
      -auto-approve \
      -input=false
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
  output_type="${3}"

  if [[ ! -d "${terraservice}" ]]; then
    echo "${terraservice} directory doesn't exist or is not readable"
    return 1
  fi

  local output
  if ! output="$(terraform -chdir="${terraservice}" init)"; then
    echo "Error while initializing ${terraservice} to get ${output_name} output: ${output}"
    return 1
  fi

  local -a output_command=(terraform -chdir="${terraservice}" output)
  if [[ "${output_type}" == "json" ]]; then
    output_command+=(-json)
  elif [[ "${output_type}" == "raw" ]]; then
    output_command+=(-raw)
  fi
  output_command+=("${output_name}")

  if ! output="$(
    "${output_command[@]}"
  )"; then
    echo "Error while getting ${output_name} output: ${output}. Output command: ${output_command[*]}"
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
  if grep -q "${configuration_variable_name}" "${destination_file_path}"; then
    echo "${configuration_variable_name} is already in ${destination_file_path}"
  else
    echo "Adding ${configuration_variable_name} to ${destination_file_path}"
    echo "${configuration_variable}" >>"${destination_file_path}"
  fi
  terraform fmt "${destination_file_path}"
}

remove_terraform_configuration_variable_from_file() {
  local configuration_variable="${1}"
  local destination_file_path="${2}"
  local configuration_variable_name

  configuration_variable_name="$(echo "${configuration_variable}" | awk ' { print $1 }')"
  echo "Removing ${configuration_variable_name} from ${destination_file_path}"
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

get_kubernetes_load_balancer_service_external_ip_address_or_wait() {
  local SERVICE_NAME="${1}"
  local SERVICE_NAMESPACE="${2}"
  local SERVICE_IP_ADDRESS_VARIABLE_NAME="${3}"
  local -n SERVICE_IP_ADDRESS="${SERVICE_IP_ADDRESS_VARIABLE_NAME}"
  while [[ -z "${SERVICE_IP_ADDRESS:-}" ]]; do
    echo "Waiting for ${SERVICE_NAME} (namespace: ${SERVICE_NAMESPACE}) to have an external IP address..."
    if ! SERVICE_IP_ADDRESS="$(kubectl get svc "${SERVICE_NAME}" -n "${SERVICE_NAMESPACE}" --template="{{range .status.loadBalancer.ingress}}{{.ip}}{{end}}")"; then
      echo "${SERVICE_NAME} (namespace: ${SERVICE_NAMESPACE}) not ready yet, waiting"
    fi
    [[ -z "${SERVICE_IP_ADDRESS:-}" ]] && sleep 10
  done
  unset -n SERVICE_IP_ADDRESS
}
