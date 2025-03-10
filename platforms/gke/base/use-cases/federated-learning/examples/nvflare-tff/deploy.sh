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
SCRIPT_DIRECTORY_PATH="$(dirname "${0}")"

echo "This script (${SCRIPT_BASENAME}) has been invoked with: $0 $*"
echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"

WORKLOAD_NAMES_DESCRIPTION="Names of the workloads to deploy, separated by a space"

usage() {
  echo
  echo "${SCRIPT_BASENAME} - This script deploys the NVIDIA FLARE example"
  echo
  echo "USAGE"
  echo "  ${SCRIPT_BASENAME} [options]"
  echo
  echo "OPTIONS"
  echo "  -h $(is_linux && echo "| --help"): ${HELP_DESCRIPTION}"
  echo "  -w $(is_linux && echo "| --workload-names"): ${WORKLOAD_NAMES_DESCRIPTION}. Remember to double-quote the value. Example: \"client1 client2\""
  echo
  echo "EXIT STATUS"
  echo
  echo "  ${EXIT_OK} on correct execution."
  echo "  ${EXIT_GENERIC_ERR} on a generic error."
  echo "  ${ERR_ARGUMENT_EVAL_ERROR} when a parameter or a variable is not defined, or empty."
  echo "  ${ERR_MISSING_DEPENDENCY} when a required dependency is missing."
  echo "  ${ERR_ARGUMENT_EVAL_ERROR} when there was an error while evaluating the program options."
}

LONG_OPTIONS="help,workload-names:"
SHORT_OPTIONS="hw:"

# BSD getopt (bundled in MacOS) doesn't support long options, and has different parameters than GNU getopt
if is_linux; then
  TEMP="$(getopt -o "${SHORT_OPTIONS}" --long "${LONG_OPTIONS}" -n "${SCRIPT_BASENAME}" -- "$@")"
elif is_macos; then
  TEMP="$(getopt "${SHORT_OPTIONS} --" "$@")"
  echo "WARNING: Long command line options are not supported on this system."
fi
RET_CODE=$?
if [ ! ${RET_CODE} ]; then
  echo "Error while evaluating command options. Terminating..."
  exit "${ERR_ARGUMENT_EVAL_ERROR}"
fi
eval set -- "${TEMP}"

WORKLOAD_NAMES=""
while true; do
  case "${1}" in
  -w | --workload-name)
    WORKLOAD_NAMES="${2}"
    shift 2
    ;;
  --)
    shift
    break
    ;;
  -h | --help | *)
    usage
    exit "${EXIT_OK}"
    ;;
  esac
done

if ! check_optional_argument "${WORKLOAD_NAMES}" "${WORKLOAD_NAMES_DESCRIPTION}"; then
  WORKLOAD_NAMES="client1 client2 server1"
fi

declare -a WORKLOADS_TO_DEPLOY
ParseSpaceSeparatedBashArray "${WORKLOAD_NAMES}" "WORKLOADS_TO_DEPLOY"

# Add double quotes for terraform strings
for i in "${!WORKLOADS_TO_DEPLOY[@]}"; do
  WORKLOADS_TO_DEPLOY["$i"]="\"${WORKLOADS_TO_DEPLOY["$i"]}\","
done
echo "WORKLOADS_TO_DEPLOY: ${WORKLOADS_TO_DEPLOY[*]}"

start_timestamp_federated_learning=$(date +%s)

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
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_workloads_to_deploy_placeholder" "[ ${WORKLOADS_TO_DEPLOY[*]}, ]" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"

echo "Running the Federated learning use case provisioning script again because we updated the reference architecture configuration"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
