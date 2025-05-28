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

echo "Setting up the environment for the cross-device federated learning example"
CROSS_DEVICE_EXAMPLE_TENANT_NAME="fl-1"
CROSS_DEVICE_MODEL_BUCKET="model-0"
CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET="aggregated-gradient-0"
CROSS_DEVICE_CLIENT_GRADIENT_BUCKET="client-gradient-0"
CROSS_DEVICE_AGGREGATOR_SERVICE_ACCOUNT="aggregator"
CROSS_DEVICE_MODELUPDATER_SERVICE_ACCOUNT="modelupdater"
CROSS_DEVICE_COLLECTOR_SERVICE_ACCOUNT="collector"
CROSS_DEVICE_TASK_ASSIGNMENT_SERVICE_ACCOUNT="task-assignment"
CROSS_DEVICE_TASK_MANAGEMENT_SERVICE_ACCOUNT="task-management"
CROSS_DEVICE_TASK_SCHEDULER_SERVICE_ACCOUNT="task-scheduler"
CROSS_DEVICE_TASK_BUILDER_SERVICE_ACCOUNT="task-builder"
CROSS_DEVICE_AGGREGATOR_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/aggregator_image@sha256:1043eb980b618e325d5b490c879fc72f211a70104d7f645b1bbb70996a42de2c"
CROSS_DEVICE_MODELUPDATER_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/model_updater_image@sha256:b0bc213e4cb34c99525345b1d544371ce5c9d647ec08405a9ca96d61e0b272fa"
CROSS_DEVICE_COLLECTOR_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/collector_image"
CROSS_DEVICE_TASK_ASSIGNMENT_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/task_assignment_image"
CROSS_DEVICE_TASK_MANAGEMENT_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/task_management_image"
CROSS_DEVICE_TASK_SCHEDULER_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/task_scheduler_image"
CROSS_DEVICE_TASK_BUILDER_IMAGE="europe-docker.pkg.dev/driven-density-457716-m7/container-image-repository/task_builder_image"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_CROSS_DEVICE_EXAMPLE_CONFIG_AUTO_VARS_FILE="${FEDERATED_LEARNING_SHARED_CONFIG_DIR}/uc_federated_learning_cross_device_example.auto.tfvars"

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES=(
  "federated_learning_tenant_names = [\"${CROSS_DEVICE_EXAMPLE_TENANT_NAME}\"]"
  "federated_learning_cloud_storage_buckets = {\"${CROSS_DEVICE_MODEL_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"},\"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"},\"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\"={force_destroy=true,versioning_enabled=false,public_access_prevention=\"enforced\"}}"
  "federated_learning_cloud_storage_buckets_iam_bindings = [{bucket_name=\"${CROSS_DEVICE_MODEL_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"},{bucket_name=\"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"},{bucket_name=\"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\",member=\"federated_learning_cross_device_apps_service_account_placeholder\",role=\"roles/storage.objectUser\"}]"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES=(
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES=(
  "federated_learning_confidential_space_instance_image_name = \"projects/confidential-space-images/global/images/confidential-space-debug-250301\""
  "federated_learning_cross_device_allowed_operator_service_accounts = \"ca-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com,cb-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com\""
  "federated_learning_model_bucket = \"${CROSS_DEVICE_MODEL_BUCKET}\""
  "federated_learning_aggregated_gradient_bucket = \"${CROSS_DEVICE_AGGREGATED_GRADIENT_BUCKET}\""
  "federated_learning_client_gradient_bucket = \"${CROSS_DEVICE_CLIENT_GRADIENT_BUCKET}\""
  "federated_learning_confidential_space_aggregator_service_account = \"${CROSS_DEVICE_AGGREGATOR_SERVICE_ACCOUNT}\""
  "federated_learning_confidential_space_modelupdater_service_account = \"${CROSS_DEVICE_MODELUPDATER_SERVICE_ACCOUNT}\""
  "federated_learning_collector_service_account = \"${CROSS_DEVICE_COLLECTOR_SERVICE_ACCOUNT}\""
  "federated_learning_task_assignment_service_account = \"${CROSS_DEVICE_TASK_ASSIGNMENT_SERVICE_ACCOUNT}\""
  "federated_learning_task_management_service_account = \"${CROSS_DEVICE_TASK_MANAGEMENT_SERVICE_ACCOUNT}\""
  "federated_learning_task_scheduler_service_account = \"${CROSS_DEVICE_TASK_SCHEDULER_SERVICE_ACCOUNT}\""
  "federated_learning_task_builder_service_account = \"${CROSS_DEVICE_TASK_BUILDER_SERVICE_ACCOUNT}\""
  "federated_learning_confidential_space_workloads = {\"aggregator\"={workload_image = \"${CROSS_DEVICE_AGGREGATOR_IMAGE}\",service_account=\"${CROSS_DEVICE_AGGREGATOR_SERVICE_ACCOUNT}\",min_replicas=2,max_replicas=5,cooldown_period=180,autoscaling_jobs_per_instance=2,machine_type=\"n2d-standard-8\"},\"modelupdater\"={workload_image=\"${CROSS_DEVICE_MODELUPDATER_IMAGE}\",service_account=\"${CROSS_DEVICE_MODELUPDATER_SERVICE_ACCOUNT}\",min_replicas=2,max_replicas=5,cooldown_period=120,autoscaling_jobs_per_instance=2,machine_type=\"n2d-standard-8\"}}"
  "federated_learning_encryption_key_service_a_base_url = \"https://privatekeyservice-ca-staging.rb-odp-key-host-dev.com/v1alpha\""
  "federated_learning_encryption_key_service_b_base_url = \"https://privatekeyservice-cb-staging.rb-odp-key-host-dev.com/v1alpha\""
  "federated_learning_encryption_key_service_a_cloudfunction_url = \"https://ca-staging-us-central1-encryption-key-service-clo-2q6l4c4evq-uc.a.run.app\""
  "federated_learning_encryption_key_service_b_cloudfunction_url = \"https://cb-staging-us-central1-encryption-key-service-clo-2q6l4c4evq-uc.a.run.app\""
  "federated_learning_wip_provider_a = \"projects/586348853457/locations/global/workloadIdentityPools/ca-staging-opwip-1/providers/ca-staging-opwip-pvdr-1\""
  "federated_learning_wip_provider_b = \"projects/586348853457/locations/global/workloadIdentityPools/cb-staging-opwip-1/providers/cb-staging-opwip-pvdr-1\""
  "federated_learning_service_account_a = \"ca-staging-opverifiedusr@rb-odp-key-host.iam.gserviceaccount.com\""
  "federated_learning_service_account_b = \"cb-staging-opverifiedusr@rb-odp-key-host.iam.gserviceaccount.com\""
  "federated_learning_cross_device_allowed_operator_service_accounts = \"ca-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com,cb-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com\""
  "federated_learning_aggregator_image = \"${CROSS_DEVICE_AGGREGATOR_IMAGE}\""
  "federated_learning_modelupdater_image = \"${CROSS_DEVICE_MODELUPDATER_IMAGE}\""
  "federated_learning_collector_image = \"${CROSS_DEVICE_COLLECTOR_IMAGE}\""
  "federated_learning_task_assignment_image = \"${CROSS_DEVICE_TASK_ASSIGNMENT_IMAGE}\""
  "federated_learning_task_management_image = \"${CROSS_DEVICE_TASK_MANAGEMENT_IMAGE}\""
  "federated_learning_task_scheduler_image = \"${CROSS_DEVICE_TASK_SCHEDULER_IMAGE}\""
  "federated_learning_task_builder_image = \"${CROSS_DEVICE_TASK_BUILDER_IMAGE}\""
)

# shellcheck disable=SC2034 # Variable is used in other scripts
cross_device_example_terraservices=(
  "cloud_storage"
  "spanner"
  "pubsub"
  "service_account_cross_device"
  "confidential_space"
  "secret_manager"
  # "example_cross_device"
)

load_fl_terraform_outputs() {
  echo "Loading container_image_repository_fully_qualified_hostname Terraform output"
  if ! CROSS_DEVICE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_HOSTNAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" "container_image_repository_fully_qualified_hostname" "raw")"; then
    exit 1
  fi
  echo "Loading container_image_repository_name Terraform output"
  if ! CROSS_DEVICE_EXAMPLE_CONTAINER_IMAGE_REPOSITORY_NAME="$(get_terraform_output "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/container_image_repository" "container_image_repository_name" "raw")"; then
    exit 1
  fi
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
