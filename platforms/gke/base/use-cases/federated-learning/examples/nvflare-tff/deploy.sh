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

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"

CLIENT_1_IP_ADDRESS_DESCRIPTION="Client 1 IP address"
CLIENT_2_IP_ADDRESS_DESCRIPTION="Client 2 IP address"
WORKLOAD_NAME_DESCRIPTION="Name of the workload to deploy"
WORKSPACE_BUCKET_NAME_DESCRIPTION="Name of the NVIDIA FLARE workspace Cloud Storage bucket"
SERVER_IP_ADDRESS_DESCRIPTION="IPv4 address of the NVIDIA FLARE server"

usage() {
  echo
  echo "${SCRIPT_BASENAME} - This script deploys the NVIDIA FLARE example"
  echo
  echo "USAGE"
  echo "  ${SCRIPT_BASENAME} [options]"
  echo
  echo "OPTIONS"
  echo "  -b $(is_linux && echo "| --workspace-bucket-name"): ${WORKSPACE_BUCKET_NAME_DESCRIPTION}"
  echo "  -c $(is_linux && echo "| --client1-ip"): ${CLIENT_1_IP_ADDRESS_DESCRIPTION}"
  echo "  -d $(is_linux && echo "| --client2-ip"): ${CLIENT_2_IP_ADDRESS_DESCRIPTION}"
  echo "  -h $(is_linux && echo "| --help"): ${HELP_DESCRIPTION}"
  echo "  -s $(is_linux && echo "| --server-ip"): ${SERVER_IP_ADDRESS_DESCRIPTION}"
  echo "  -w $(is_linux && echo "| --workload-name"): ${WORKLOAD_NAME_DESCRIPTION}"
  echo
  echo "EXIT STATUS"
  echo
  echo "  ${EXIT_OK} on correct execution."
  echo "  ${EXIT_GENERIC_ERR} on a generic error."
  echo "  ${ERR_ARGUMENT_EVAL_ERROR} when a parameter or a variable is not defined, or empty."
  echo "  ${ERR_MISSING_DEPENDENCY} when a required dependency is missing."
  echo "  ${ERR_ARGUMENT_EVAL_ERROR} when there was an error while evaluating the program options."
}

LONG_OPTIONS="help,client1-ip:,client2-ip:,server-ip:,workspace-bucket-name:,workload-name:"
SHORT_OPTIONS="b:c:d:hs:w:"

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

WORKLOAD_NAME=""
while true; do
  case "${1}" in
  -b | --workspace-bucket-name)
    NVFLARE_WORKSPACE_BUCKET_NAME_INPUT="${2}"
    shift 2
    ;;
  -c | --client1-ip)
    CLIENT_1_IP_ADDRESS="${2}"
    shift 2
    ;;
  -d | --client2-ip)
    CLIENT_2_IP_ADDRESS="${2}"
    shift 2
    ;;
  -s | --server-ip)
    SERVER_IP_ADDRESS="${2}"
    shift 2
    ;;
  -w | --workload-name)
    WORKLOAD_NAME="${2}"
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

check_argument "${WORKLOAD_NAME}" "${WORKLOAD_NAME_DESCRIPTION}"

if [[ "${WORKLOAD_NAME}" == "server1" ]]; then
  check_optional_argument "${CLIENT_1_IP_ADDRESS:-}" "${CLIENT_1_IP_ADDRESS_DESCRIPTION}" || true
  check_optional_argument "${CLIENT_2_IP_ADDRESS:-}" "${CLIENT_2_IP_ADDRESS_DESCRIPTION}" || true
else
  check_argument "${NVFLARE_WORKSPACE_BUCKET_NAME_INPUT:-}" "${WORKSPACE_BUCKET_NAME_DESCRIPTION}"
  check_argument "${SERVER_IP_ADDRESS:-}" "${SERVER_IP_ADDRESS_DESCRIPTION}"
fi

start_timestamp_federated_learning=$(date +%s)

echo "Preparing the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  if [[ "${WORKLOAD_NAME}" != "server1" ]] &&
    [[ "${configuration_variable}" =~ ^federated_learning_cloud_storage_buckets* ]]; then
    echo "${WORKLOAD_NAME} is not server1. Skip setting the configuration variable: ${configuration_variable}"
    continue
  fi
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case provisioning script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

echo "Refreshing the environment configuration"
load_fl_terraform_outputs

echo "Updating the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  # Check if the configuration variable is not applicable to servers or clients
  if [[ "${WORKLOAD_NAME}" == "server1" ]]; then
    if [[ "${configuration_variable}" =~ ^federated_learning_nvidia_flare_tff_example_server* ]]; then
      echo "Skip setting configuration variable for ${WORKLOAD_NAME} because it's not applicable to servers: ${configuration_variable}"
      continue
    fi

    if [[ "${configuration_variable}" =~ ^federated_learning_nvidia_flare_tff_example_client* ]] &&
      [[ (-z "${CLIENT_1_IP_ADDRESS:-}" || -z "${CLIENT_2_IP_ADDRESS:-}") ]]; then
      echo "Skip setting configuration variable for ${WORKLOAD_NAME} because it's applicable to servers but client IP addresses are not set: ${configuration_variable}"
      continue
    fi
  else
    if [[ "${configuration_variable}" =~ ^federated_learning_cloud_storage_buckets_iam_bindings*|^federated_learning_nvidia_flare_tff_example_client* ]]; then
      echo "Skip setting configuration variable for ${WORKLOAD_NAME} because it's not applicable to clients: ${configuration_variable}"
      continue
    fi
  fi

  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Updating the reference architecture configuration values to deploy the NVIDIA FLARE TFF example"

if [[ "${WORKLOAD_NAME}" != "server1" ]]; then
  echo "Getting NVFLARE workspace bucket name from script inputs: ${NVFLARE_WORKSPACE_BUCKET_NAME_INPUT}"
  NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME="${NVFLARE_WORKSPACE_BUCKET_NAME_INPUT}"
fi

edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_apps_service_account_placeholder" "${NVFLARE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_bucket_name_placeholder" "${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_TAG}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_workload_to_deploy_placeholder" "${WORKLOAD_NAME}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"

if [[ "${WORKLOAD_NAME}" == "server1" ]]; then
  # Check if the variables to substitute to placeholders have been set because they are optional input parameters
  [[ -n "${CLIENT_1_IP_ADDRESS:-""}" ]] && edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_client1_a_rrdatas_placeholder" "\"${CLIENT_1_IP_ADDRESS}\"" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
  [[ -n "${CLIENT_2_IP_ADDRESS:-""}" ]] && edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_client2_a_rrdatas_placeholder" "\"${CLIENT_2_IP_ADDRESS}\"" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
else
  edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_server1_a_rrdatas_placeholder" "\"${SERVER_IP_ADDRESS}\"" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
fi

echo "Provision services that the NVIDIA FLARE TFF example depends on"
# shellcheck disable=SC2154 # variable defined in setup-environment.sh
for terraservice in "${nvflare_example_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

provision_terraservice "config_management"

echo "Building the NVIDIA FLARE container image"
"${FEDERATED_LEARNING_USE_CASE_DIR}/examples/nvflare-tff/build-container-image.sh"

if [[ "${WORKLOAD_NAME}" == "server1" ]]; then
  if [[ ! -d "${NVFLARE_GENERATED_WORKSPACE_PATH}" ]]; then
    echo "Generating NVFLARE workspace files in ${NVFLARE_WORKSPACE_PATH}"
    sudo chown -R 10000:10000 "${NVFLARE_WORKSPACE_PATH}"
    docker run --rm -v "${NVFLARE_WORKSPACE_PATH}:/opt/NVFlare/workspace" -it "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" nvflare provision
    sudo chown -R "$(id -u)":"$(id -g)" "${NVFLARE_WORKSPACE_PATH}"
    gcloud storage cp --recursive "${NVFLARE_GENERATED_WORKSPACE_PATH}" "gs://${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}"
  else
    echo "Skip generating the NVFLARE workspace because it was already generated"
  fi
fi

"${FEDERATED_LEARNING_USE_CASE_DIR}/examples/nvflare-tff/push-container-image.sh"

if [[ "${WORKLOAD_NAME}" == "server1" ]]; then
  # shellcheck disable=SC2154 # variable defined in setup-environment.sh
  gcloud container clusters get-credentials "${cluster_name}" \
    --region "${cluster_region}" \
    --project "${cluster_project_id}" \
    --dns-endpoint

  while [[ -z "${SERVER_IP_ADDRESS:-}" ]]; do
    echo "Waiting for the ingress gateway to have an external IP address..."
    SERVER_IP_ADDRESS=$(kubectl get svc istio-ingressgateway -n istio-ingress --template="{{range .status.loadBalancer.ingress}}{{.ip}}{{end}}")
    [[ -z "${SERVER_IP_ADDRESS:-}" ]] && sleep 10
  done

  echo "NVFLARE workspace bucket name: ${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}"
  echo "NVFLARE server IP address: ${SERVER_IP_ADDRESS}"
fi

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
