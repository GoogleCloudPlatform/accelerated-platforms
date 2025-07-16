#!/usr/bin/env bash
#
# Copyright 2025 Google LLC
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

echo "Setting up the environment for the cross-device federated learning example"
CROSS_DEVICE_EXAMPLE_TENANT_NAME="fl-1"
CROSS_DEVICE_MODEL_BUCKET="m-0"
CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET="ag-0"
CROSS_DEVICE_CLIENT_GRADIENT_BUCKET="cg-0"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_CROSS_DEVICE_EXAMPLE_CONFIG_AUTO_VARS_FILE="${FEDERATED_LEARNING_SHARED_CONFIG_DIR}/uc_federated_learning_cross_device_example.auto.tfvars"

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES=(
  "federated_learning_tenant_names = [\"${CROSS_DEVICE_EXAMPLE_TENANT_NAME}\"]"
  "federated_learning_cloud_storage_buckets = {\"${CROSS_DEVICE_MODEL_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"},\"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"},\"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"}}"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES=(
  "federated_learning_cloud_storage_buckets_iam_bindings = [{bucket_name=\"${CROSS_DEVICE_MODEL_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"},{bucket_name=\"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"},{bucket_name=\"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"}]"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES=(
  "federated_learning_cross_device_example_model_bucket = \"${CROSS_DEVICE_MODEL_BUCKET}\""
  "federated_learning_cross_device_example_aggregated_gradient_bucket = \"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\""
  "federated_learning_cross_device_example_client_gradient_bucket = \"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\""
  "federated_learning_cross_device_example_confidential_space_workloads = {\"aggregator\"={min_replicas=2,max_replicas=5,cooldown_period=180,autoscaling_jobs_per_instance=2,machine_type=\"n2d-standard-8\"},\"modelupdater\"={min_replicas=2,max_replicas=5,cooldown_period=120,autoscaling_jobs_per_instance=2,machine_type=\"n2d-standard-8\"}}"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
cross_device_example_terraservices=(
  "spanner"
  "pubsub"
  "confidential_space"
  "build_workload_images"
  "secret_manager"
  "network"
)

load_fl_terraform_outputs() {
  echo "Loading workload_identity_principal_prefix Terraform output"
  if ! CROSS_DEVICE_EXAMPLE_CLUSTER_WORKLOAD_IDENTITY_PRINCIPAL_PREFIX="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/service_account" "workload_identity_principal_prefix" "raw")"; then
    exit 1
  fi
  echo "Loading federated_learning_kubernetes_service_account_name Terraform output"
  if ! CROSS_DEVICE_EXAMPLE_KUBERNETES_SERVICE_ACCOUNT_NAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/service_account" "federated_learning_kubernetes_service_account_name" "raw")"; then
    exit 1
  fi
  # shellcheck disable=SC2034 # Variable is used in other scripts
  CROSS_DEVICE_EXAMPLE_APPS_SERVICE_ACCOUNT_IAM_EMAIL="${CROSS_DEVICE_EXAMPLE_CLUSTER_WORKLOAD_IDENTITY_PRINCIPAL_PREFIX}/ns/${CROSS_DEVICE_EXAMPLE_TENANT_NAME}/sa/${CROSS_DEVICE_EXAMPLE_KUBERNETES_SERVICE_ACCOUNT_NAME}"
}
