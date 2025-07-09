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

locals {
  federated_learning_cross_device_example_spanner_instance_name      = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_spanner_instance_name])
  federated_learning_cross_device_example_spanner_database_name      = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_spanner_database_name])
  federated_learning_cross_device_example_spanner_lock_database_name = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_spanner_lock_database_name])

  federated_learning_cross_device_example_aggregator_pubsub_name                       = var.federated_learning_cross_device_example_aggregator_pubsub_name
  federated_learning_cross_device_example_aggregator_pubsub_topic                      = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_aggregator_pubsub_name, "topic"])
  federated_learning_cross_device_example_aggregator_pubsub_subscription               = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_aggregator_pubsub_name, "subscription"])
  federated_learning_cross_device_example_modelupdater_pubsub_name                     = var.federated_learning_cross_device_example_modelupdater_pubsub_name
  federated_learning_cross_device_example_modelupdater_pubsub_topic                    = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_modelupdater_pubsub_name, "topic"])
  federated_learning_cross_device_example_modelupdater_pubsub_subscription             = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_modelupdater_pubsub_name, "subscription"])
  federated_learning_cross_device_example_aggregator_notifications_pubsub_name         = join("-", [local.federated_learning_cross_device_example_aggregator_pubsub_name, "notifications"])
  federated_learning_cross_device_example_aggregator_notifications_pubsub_topic        = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_aggregator_notifications_pubsub_name, "topic"])
  federated_learning_cross_device_example_aggregator_notifications_pubsub_subscription = join("-", [local.unique_identifier_prefix, local.federated_learning_cross_device_example_aggregator_notifications_pubsub_name, "subscription"])

  federated_learning_pubsub_topics = [local.federated_learning_cross_device_example_aggregator_pubsub_name, local.federated_learning_cross_device_example_modelupdater_pubsub_name, local.federated_learning_cross_device_example_aggregator_notifications_pubsub_name]

  federated_learning_cross_device_example_client_gradient_bucket_name     = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_client_gradient_bucket])
  federated_learning_cross_device_example_aggregated_gradient_bucket_name = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_aggregated_gradient_bucket])
  federated_learning_cross_device_example_model_bucket_name               = join("-", [local.unique_identifier_prefix, var.federated_learning_cross_device_example_model_bucket])

  cross_device_confidential_space_aggregator_service_account   = var.federated_learning_cross_device_confidential_space_aggregator_service_account
  cross_device_confidential_space_modelupdater_service_account = var.federated_learning_cross_device_confidential_space_modelupdater_service_account

  cross_device_confidential_space_service_accounts = [
    local.cross_device_confidential_space_aggregator_service_account,
    local.cross_device_confidential_space_modelupdater_service_account
  ]

  cross_device_collector_service_account       = var.federated_learning_cross_device_collector_service_account
  cross_device_task_assignment_service_account = var.federated_learning_cross_device_task_assignment_service_account
  cross_device_task_management_service_account = var.federated_learning_cross_device_task_management_service_account
  cross_device_task_scheduler_service_account  = var.federated_learning_cross_device_task_scheduler_service_account
  cross_device_task_builder_service_account    = var.federated_learning_cross_device_task_builder_service_account

  cross_device_service_accounts = [
    local.cross_device_collector_service_account,
    local.cross_device_task_assignment_service_account,
    local.cross_device_task_management_service_account,
    local.cross_device_task_scheduler_service_account,
    local.cross_device_task_builder_service_account
  ]

  cross_device_common_roles = [
    "roles/logging.logWriter",
    "roles/iam.serviceAccountTokenCreator",
    "roles/storage.objectUser",
    "roles/pubsub.subscriber",
    "roles/pubsub.publisher",
    "roles/secretmanager.secretAccessor"
  ]

  cross_device_confidential_space_roles = [
    "roles/iam.serviceAccountUser",
    "roles/confidentialcomputing.workloadUser",
    "roles/monitoring.viewer",
    "roles/monitoring.metricWriter",
    "roles/artifactregistry.reader"
  ]

  cross_device_workload_roles = [
    "roles/spanner.databaseUser",
    "roles/gkehub.serviceAgent",
    "roles/iam.workloadIdentityUser"
  ]
}

## Federated Learning bucket names
variable "federated_learning_cross_device_example_client_gradient_bucket" {
  description = "Client gradient bucket name"
  type        = string
}

variable "federated_learning_cross_device_example_aggregated_gradient_bucket" {
  description = "Aggregated gradient bucket name"
  type        = string
}

variable "federated_learning_cross_device_example_model_bucket" {
  description = "Model bucket name"
  type        = string
}

## Federated Learning Spanner variables
variable "federated_learning_cross_device_example_spanner_instance_name" {
  description = "Name of the Spanner instance"
  type        = string
  default     = "instance"
}

variable "federated_learning_cross_device_example_spanner_database_name" {
  description = "Name of the Spanner database"
  type        = string
  default     = "database"
}

variable "federated_learning_cross_device_example_spanner_lock_database_name" {
  description = "Name of the Spanner lock database"
  type        = string
  default     = "lock-database"
}

## Federated Learning pubsub variables
variable "federated_learning_cross_device_example_aggregator_pubsub_name" {
  description = "Aggregator topic to be created for the cross-device example"
  type        = string
  default     = "aggregator"
}

variable "federated_learning_cross_device_example_modelupdater_pubsub_name" {
  description = "Modelupdater topic to be created for the cross-device example"
  type        = string
  default     = "modelupdater"
}

## Keys service
variable "federated_learning_cross_device_example_encryption_key_service_a_base_url" {
  description = "The base url of the encryption key service A."
  type        = string
}

variable "federated_learning_cross_device_example_encryption_key_service_b_base_url" {
  description = "The base url of the encryption key service B."
  type        = string
}

variable "federated_learning_cross_device_example_encryption_key_service_a_cloudfunction_url" {
  description = "The cloudfunction url of the encryption key service A."
  type        = string
}

variable "federated_learning_cross_device_example_encryption_key_service_b_cloudfunction_url" {
  description = "The cloudfunction url of the encryption key service B."
  type        = string
}

variable "federated_learning_cross_device_example_wip_provider_a" {
  description = "The workload identity provider of the encryption key service A."
  type        = string
}

variable "federated_learning_cross_device_example_wip_provider_b" {
  description = "The workload identity provider of the encryption key service B."
  type        = string
}

variable "federated_learning_cross_device_example_service_account_a" {
  description = "The service account to impersonate of the encryption key service A."
  type        = string
}

variable "federated_learning_cross_device_example_service_account_b" {
  description = "The service account to impersonate of the encryption key service B."
  type        = string
}

## Service accounts
variable "federated_learning_cross_device_confidential_space_aggregator_service_account" {
  description = "Name of the aggregator service account to allowlist in the coordinator"
  type        = string
  default     = "aggregator"
}

variable "federated_learning_cross_device_confidential_space_modelupdater_service_account" {
  description = "Name of the model updater service account to allowlist in the coordinator"
  type        = string
  default     = "modelupdater"
}

variable "federated_learning_cross_device_collector_service_account" {
  description = "Name of the collector service account"
  type        = string
  default     = "collector"
}

variable "federated_learning_cross_device_task_assignment_service_account" {
  description = "Name of the task assignment service account"
  type        = string
  default     = "task-assignment"
}

variable "federated_learning_cross_device_task_management_service_account" {
  description = "Name of the task management service account"
  type        = string
  default     = "task-management"
}

variable "federated_learning_cross_device_task_scheduler_service_account" {
  description = "Name of the task scheduler service account"
  type        = string
  default     = "task-scheduler"
}

variable "federated_learning_cross_device_task_builder_service_account" {
  description = "Name of the task builder service account"
  type        = string
  default     = "task-builder"
}

## Misc
variable "federated_learning_cross_device_example_download_plan_token_duration" {
  description = "Duration in seconds the download plan signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_cross_device_example_download_checkpoint_token_duration" {
  description = "Duration in seconds the download checkpoint signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_cross_device_example_upload_gradient_token_duration" {
  description = "Duration in seconds the upload gradient signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_cross_device_example_allow_rooted_devices" {
  description = "Whether to allow rooted devices. This setting will have no effect when authentication is disabled. It is recommended to be set false for production environments."
  type        = bool
  default     = false
}

variable "federated_learning_cross_device_example_is_authentication_enabled" {
  description = "Whether to enable authentication"
  type        = bool
  default     = false
}

variable "federated_learning_cross_device_example_local_compute_timeout_minutes" {
  description = "The duration an assignment will remain in ASSIGNED status before timing out in minutes."
  type        = number
  default     = 15
}

variable "federated_learning_cross_device_example_upload_timeout_minutes" {
  description = "The duration an assignment will remain in LOCAL_COMPLETED status before timing out in minutes."
  type        = number
  default     = 15
}

variable "federated_learning_cross_device_example_aggregation_batch_failure_threshold" {
  description = "The number of aggregation batches failed for an iteration before moving the iteration to a failure state."
  type        = number
  default     = 3
}

variable "federated_learning_cross_device_example_collector_batch_size" {
  description = "The size of aggregation batches created by the collector"
  type        = number
  default     = 50
}
