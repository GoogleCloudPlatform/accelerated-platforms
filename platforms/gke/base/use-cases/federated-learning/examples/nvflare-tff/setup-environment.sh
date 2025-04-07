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

if [[ ! -v ACP_REPO_DIR ]]; then
  SCRIPT_DIRECTORY_PATH="$(cd -P "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

  echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

  ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../../../")"
  export ACP_REPO_DIR
  export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"

  echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
  echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"

  export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
  echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

echo "Setting up the environment for the NVIDIA FLARE federated learning example"

NVFLARE_EXAMPLE_TENANT_NAME="fl-1"

NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME="nvf-ws"

NVFLARE_WORKSPACE_PATH="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/example_nvidia_flare_tff/nvflare-workspace"
# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_GENERATED_WORKSPACE_PATH="${NVFLARE_WORKSPACE_PATH}/workspace"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_NVFLARE_EXAMPLE_CONFIG_AUTO_VARS_FILE="${FEDERATED_LEARNING_SHARED_CONFIG_DIR}/uc_federated_learning_nvflare_example.auto.tfvars"

# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES=(
  "federated_learning_tenant_names = [\"${NVFLARE_EXAMPLE_TENANT_NAME}\"]"
  "federated_learning_cloud_storage_buckets = {\"${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME}\" = { force_destroy = true, versioning_enabled = false }}"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES=(
  "federated_learning_cloud_storage_buckets_iam_bindings = [ {bucket_name = \"${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME}\", member = \"federated_learning_nvidia_flare_tff_apps_service_account_placeholder\", role = \"roles/storage.objectUser\"} ]"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES=(
  "federated_learning_nvidia_flare_tff_example_bucket_name = \"federated_learning_nvidia_flare_tff_example_bucket_name_placeholder\""
  "federated_learning_nvidia_flare_tff_example_container_image_tag = \"federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder\""
  "federated_learning_nvidia_flare_tff_example_localized_container_image_id = \"federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder\""
  "federated_learning_nvidia_flare_tff_example_tenant_name = \"${NVFLARE_EXAMPLE_TENANT_NAME}\""
  "federated_learning_nvidia_flare_tff_example_workload_to_deploy = \"federated_learning_nvidia_flare_tff_example_workload_to_deploy_placeholder\""
)

# shellcheck disable=SC2034 # Variable is used in other scripts
nvflare_example_terraservices=(
  "example_nvidia_flare_tff"
)

load_fl_terraform_outputs() {
  echo "Loading container_image_repository_fully_qualified_hostname Terraform output"
  if ! NVFLARE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_HOSTNAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" "container_image_repository_fully_qualified_hostname" "raw")"; then
    exit 1
  fi
  echo "Loading container_image_repository_name Terraform output"
  if ! NVFLARE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_NAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" "container_image_repository_name" "raw")"; then
    exit 1
  fi
  echo "Loading workload_identity_principal_prefix Terraform output"
  if ! NVFLARE_EXAMPLE_CLUSTER_WORKLOAD_IDENTITY_PRINCIPAL_PREFIX="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/service_account" "workload_identity_principal_prefix" "raw")"; then
    exit 1
  fi
  echo "Loading federated_learning_kubernetes_service_account_name Terraform output"
  if ! NVFLARE_EXAMPLE_KUBERNETES_SERVICE_ACCOUNT_NAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/service_account" "federated_learning_kubernetes_service_account_name" "raw")"; then
    exit 1
  fi
  # shellcheck disable=SC2034 # Variable is used in other scripts
  NVFLARE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL="${NVFLARE_EXAMPLE_CLUSTER_WORKLOAD_IDENTITY_PRINCIPAL_PREFIX}/ns/${NVFLARE_EXAMPLE_TENANT_NAME}/sa/${NVFLARE_EXAMPLE_KUBERNETES_SERVICE_ACCOUNT_NAME}"

  echo "Loading federated_learning_google_storage_bucket_names Terraform output"
  # Assume that there's only one bucket, so get the first (and only) bucket name
  # shellcheck disable=SC2034 # Variable is used in other scripts
  if ! NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/cloud_storage" "federated_learning_google_storage_bucket_names" "json" | jq --raw-output '.[0]')"; then
    exit 1
  fi

  NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID="${NVFLARE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_HOSTNAME}/${NVFLARE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_NAME}/nvflare-tensorflow"
  NVFLARE_EXAMPLE_CONTAINER_IMAGE_TAG="0.0.1"
  # shellcheck disable=SC2034 # Variable is used in other scripts
  NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG=${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID}:${NVFLARE_EXAMPLE_CONTAINER_IMAGE_TAG}
}

load_kubernetes_outputs() {
  CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS=
  get_kubernetes_load_balancer_service_external_ip_address_or_wait "istio-ingressgateway-nvflare" "istio-ingress" "CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS"
  echo "Cloud Service Mesh ingress gateway IP address: ${CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS}"
  export CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS

  NVFLARE_EXAMPLE_SERVER1_POD_NAME="$(kubectl get pods -n "${NVFLARE_EXAMPLE_TENANT_NAME}" -l run=nvflare-server1 -o jsonpath='{.items[0].metadata.name}')"
  local RET_CODE=$?
  if [[ "${RET_CODE}" -gt 0 ]]; then
    echo "Error while initializing NVFLARE_EXAMPLE_SERVER1_POD_NAME"
    return 1
  fi
  export NVFLARE_EXAMPLE_SERVER1_POD_NAME
  echo "NVIDIA FLARE server1 pod name: ${NVFLARE_EXAMPLE_SERVER1_POD_NAME}"
}
