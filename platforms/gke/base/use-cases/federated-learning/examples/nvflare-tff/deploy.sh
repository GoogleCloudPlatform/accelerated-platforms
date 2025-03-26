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

DEPLOY_EXAMPLE_DESCRIPTION="Deploy example"
WORKLOAD_NAME_DESCRIPTION="Name of the workload to deploy"

usage() {
  echo
  echo "${SCRIPT_BASENAME} - This script deploys the NVIDIA FLARE example"
  echo
  echo "USAGE"
  echo "  ${SCRIPT_BASENAME} [options]"
  echo
  echo "OPTIONS"
  echo "  -e $(is_linux && echo "| --deploy-example"): ${DEPLOY_EXAMPLE_DESCRIPTION}"
  echo "  -h $(is_linux && echo "| --help"): ${HELP_DESCRIPTION}"
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

LONG_OPTIONS="deploy-example,help,workload-name:"
SHORT_OPTIONS="ehw:"

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

DEPLOY_EXAMPLE=""
WORKLOAD_NAME=""
while true; do
  case "${1}" in
  -e | --deploy-example)
    DEPLOY_EXAMPLE="true"
    shift
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
check_optional_argument "${DEPLOY_EXAMPLE}" "${DEPLOY_EXAMPLE_DESCRIPTION}" || true

start_timestamp_federated_learning=$(date +%s)

echo "Preparing the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Running the Federated learning use case provisioning script"
"${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"

echo "Refreshing the environment configuration"
load_fl_terraform_outputs

echo "Updating the reference architecture configuration to deploy the NVIDIA FLARE TFF example"
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
done
for configuration_variable in "${NVFLARE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES[@]}"; do
  write_terraform_configuration_variable_to_file "${configuration_variable}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
done

echo "Updating the reference architecture configuration values to deploy the NVIDIA FLARE TFF example"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_apps_service_account_placeholder" "${NVFLARE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL}" "${FEDERATED_LEARNING_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_bucket_name_placeholder" "${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_TAG}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder" "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"
edit_terraform_configuration_variable_value_in_file "federated_learning_nvidia_flare_tff_example_workload_to_deploy_placeholder" "${WORKLOAD_NAME}" "${FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE}"

echo "Provision services that the NVIDIA FLARE TFF example depends on"
# shellcheck disable=SC2154 # variable defined in setup-environment.sh
for terraservice in "${nvflare_example_terraservices[@]}"; do
  provision_terraservice "${terraservice}"
done

provision_terraservice "config_management"

echo "Building the NVIDIA FLARE container image"
"${FEDERATED_LEARNING_USE_CASE_DIR}/examples/nvflare-tff/build-container-image.sh"

if [[ ! -d "${NVFLARE_GENERATED_WORKSPACE_PATH}" ]] || [[ ("${DEPLOY_EXAMPLE}" == "true" && ! -d "${NVFLARE_WORKSPACE_PATH}/workspace/example_project/prod_00/admin\@nvidia.com/transfer/hello-numpy-sag") ]]; then
  if [[ ! -d "${NVFLARE_GENERATED_WORKSPACE_PATH}" ]]; then
    echo "Generating NVFLARE workspace files in ${NVFLARE_WORKSPACE_PATH}"
    sudo chown -R 10000:10000 "${NVFLARE_WORKSPACE_PATH}"
    docker run --rm -v "${NVFLARE_WORKSPACE_PATH}:/opt/NVFlare/workspace" -it "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" nvflare provision
  fi
  if [[ ("${DEPLOY_EXAMPLE}" == "true" && ! -d "${NVFLARE_WORKSPACE_PATH}/workspace/example_project/prod_00/admin\@nvidia.com/transfer/hello-numpy-sag") ]]; then
    echo "Copying an example workload in the NVIDIA FLARE workspace"
    sudo chown -R 10000:10000 "${NVFLARE_WORKSPACE_PATH}"
    docker run --rm -it \
      -v "${NVFLARE_WORKSPACE_PATH}:/opt/NVFlare/workspace" \
      "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" \
      /bin/bash -c 'cp -R /opt/NVFlare/NVFlare-${NVFLARE_RELEASE_TAG}/examples/hello-world/hello-numpy-sag /opt/NVFlare/workspace/workspace/example_project/prod_00/admin@nvidia.com/transfer'
  fi

  sudo chown -R "$(id -u)":"$(id -g)" "${NVFLARE_WORKSPACE_PATH}"
  gcloud storage cp \
    "${NVFLARE_GENERATED_WORKSPACE_PATH}" "gs://${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}" \
    --recursive
  sudo chown -R 10000:10000 "${NVFLARE_WORKSPACE_PATH}"
else
  echo "Skip generating the NVFLARE workspace because it was already generated"
fi

"${FEDERATED_LEARNING_USE_CASE_DIR}/examples/nvflare-tff/push-container-image.sh"

# shellcheck disable=SC2154 # variable defined in setup-environment.sh
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

INGRESS_GATEWAY_IP_ADDRESS=
get_kubernetes_load_balancer_service_external_ip_address_or_wait "istio-ingressgateway-nvflare" "istio-ingress" "INGRESS_GATEWAY_IP_ADDRESS"
echo "Cloud Service Mesh ingress gateway IP address: ${INGRESS_GATEWAY_IP_ADDRESS}"

NVFLARE_SERVER_IP_ADDRESS=
get_kubernetes_load_balancer_service_external_ip_address_or_wait "nvflare-${WORKLOAD_NAME}-lb" "${NVFLARE_EXAMPLE_TENANT_NAME}" "NVFLARE_SERVER_IP_ADDRESS"
echo "NVFLARE ${WORKLOAD_NAME} external IP address: ${NVFLARE_SERVER_IP_ADDRESS}"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example deployment): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
