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

echo "Setting up the environment for the NVIDIA FLARE federated learning example"

NVFLARE_EXAMPLE_TENANT_NAME="fl-1"

NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME="nvf-ws"

# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES=(
  "federated_learning_tenant_names = [\"${NVFLARE_EXAMPLE_TENANT_NAME}\"]"
  "federated_learning_cloud_storage_buckets = {\"${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME}\" = { force_destroy = true, versioning_enabled = false }}"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
NVFLARE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES=(
  "federated_learning_cloud_storage_buckets_iam_bindings = [ {bucket_name = \"${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_BASE_NAME}\", member = \"federated_learning_nvidia_flare_tff_apps_service_account_placeholder\", role = \"roles/storage.objectUser\"} ]"
  "federated_learning_nvidia_flare_tff_example_bucket_name = \"federated_learning_nvidia_flare_tff_example_bucket_name_placeholder\""
  "federated_learning_nvidia_flare_tff_example_container_image_tag = \"federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder\""
  "federated_learning_nvidia_flare_tff_example_deploy = true"
  "federated_learning_nvidia_flare_tff_example_localized_container_image_id = \"federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder\""
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
