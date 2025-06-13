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

locals {
  spanner_instance_name      = join("-", [local.unique_identifier_prefix, var.federated_learning_spanner_instance_name])
  spanner_database_name      = join("-", [local.unique_identifier_prefix, var.federated_learning_spanner_database_name])
  spanner_lock_database_name = join("-", [local.unique_identifier_prefix, var.federated_learning_spanner_lock_database_name])

  aggregator_pubsub_name                       = var.federated_learning_aggregator_pubsub_name
  aggregator_pubsub_topic                      = join("-", [local.unique_identifier_prefix, local.aggregator_pubsub_name, "topic"])
  aggregator_pubsub_subscription               = join("-", [local.unique_identifier_prefix, local.aggregator_pubsub_name, "subscription"])
  modelupdater_pubsub_name                     = var.federated_learning_modelupdater_pubsub_name
  modelupdater_pubsub_topic                    = join("-", [local.unique_identifier_prefix, local.modelupdater_pubsub_name, "topic"])
  modelupdater_pubsub_subscription             = join("-", [local.unique_identifier_prefix, local.modelupdater_pubsub_name, "subscription"])
  aggregator_notifications_pubsub_name         = join("-", [local.aggregator_pubsub_name, "notifications"])
  aggregator_notifications_pubsub_topic        = join("-", [local.unique_identifier_prefix, local.aggregator_notifications_pubsub_name, "topic"])
  aggregator_notifications_pubsub_subscription = join("-", [local.unique_identifier_prefix, local.aggregator_notifications_pubsub_name, "subscription"])

  federated_learning_pubsub_topics = [local.aggregator_pubsub_name, local.modelupdater_pubsub_name, local.aggregator_notifications_pubsub_name]

  client_gradient_bucket_name     = var.federated_learning_client_gradient_bucket
  aggregated_gradient_bucket_name = var.federated_learning_aggregated_gradient_bucket
  model_bucket_name               = var.federated_learning_model_bucket

  confidential_space_aggregator_service_account   = var.federated_learning_confidential_space_aggregator_service_account
  confidential_space_modelupdater_service_account = var.federated_learning_confidential_space_modelupdater_service_account

  confidential_space_service_accounts = [
    local.confidential_space_aggregator_service_account,
    local.confidential_space_modelupdater_service_account
  ]

  cross_device_collector_service_account       = var.federated_learning_collector_service_account
  cross_device_task_assignment_service_account = var.federated_learning_task_assignment_service_account
  cross_device_task_management_service_account = var.federated_learning_task_management_service_account
  cross_device_task_scheduler_service_account  = var.federated_learning_task_scheduler_service_account
  cross_device_task_builder_service_account    = var.federated_learning_task_builder_service_account

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

  confidential_space_roles = [
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

variable "federated_learning_cross_device_example_deploy" {
  default     = false
  description = "Set this variable to true to deploy the Federated Learning cross device example"
  type        = bool
}

## Federated Learning bucket names
variable "federated_learning_client_gradient_bucket" {
  description = "Client gradient bucket name"
  type        = string
}

variable "federated_learning_aggregated_gradient_bucket" {
  description = "Aggregated gradient bucket name"
  type        = string
}

variable "federated_learning_model_bucket" {
  description = "Model bucket name"
  type        = string
}

## Federated Learning Spanner variables
variable "federated_learning_spanner_instance_name" {
  description = "Name of the Spanner instance"
  type        = string
  default     = "instance"
}

variable "federated_learning_spanner_database_name" {
  description = "Name of the Spanner database"
  type        = string
  default     = "database"
}

variable "federated_learning_spanner_lock_database_name" {
  description = "Name of the Spanner lock database"
  type        = string
  default     = "lock-database"
}

# Spanner configuration
variable "federated_learning_spanner_database_retention_period" {
  description = "Duration to maintain table versioning for point-in-time recovery."
  type        = string
  nullable    = false
  default     = "1h"
}

variable "federated_learning_spanner_processing_units" {
  description = "Spanner's compute capacity. 1000 processing units = 1 node and must be set as a multiple of 100."
  type        = number
  default     = 1000
}

variable "federated_learning_spanner_database_deletion_protection" {
  description = "Prevents destruction of the Spanner database."
  type        = bool
  default     = false
}

variable "federated_learning_spanner_nodes" {
  description = "Number of nodes for Spanner instance"
  type        = number
  default     = 1
}

## Federated Learning pubsub variables
variable "federated_learning_aggregator_pubsub_name" {
  description = "Aggregator topic to be created for the cross-device example"
  type        = string
  default     = "aggregator"
}

variable "federated_learning_modelupdater_pubsub_name" {
  description = "Modelupdater topic to be created for the cross-device example"
  type        = string
  default     = "modelupdater"
}

## Federated Learning confidential space variables
variable "federated_learning_confidential_space_instance_image_name" {
  description = "The Confidential Space OS source container image to run. Ref: https://cloud.google.com/confidential-computing/confidential-space/docs/confidential-space-images"
  type        = string
  default     = "projects/confidential-space-images/global/images/confidential-space-250301"
}

variable "federated_learning_confidential_space_workloads" {
  default     = {}
  description = "Map describing the Confidential Space workloads to create. Keys are virtual machine name."
  type = map(object({
    workload_image                = string
    service_account               = string
    min_replicas                  = number
    max_replicas                  = number
    cooldown_period               = number
    autoscaling_jobs_per_instance = number
    machine_type                  = string
  }))
}

variable "federated_learning_cross_device_allowed_operator_service_accounts" {
  description = "The service accounts provided by coordinator for the worker to impersonate"
  type        = string
}

## Keys service
variable "federated_learning_encryption_key_service_a_base_url" {
  description = "The base url of the encryption key service A."
  type        = string
}

variable "federated_learning_encryption_key_service_b_base_url" {
  description = "The base url of the encryption key service B."
  type        = string
}

variable "federated_learning_encryption_key_service_a_cloudfunction_url" {
  description = "The cloudfunction url of the encryption key service A."
  type        = string
}

variable "federated_learning_encryption_key_service_b_cloudfunction_url" {
  description = "The cloudfunction url of the encryption key service B."
  type        = string
}

variable "federated_learning_wip_provider_a" {
  description = "The workload identity provider of the encryption key service A."
  type        = string
}

variable "federated_learning_wip_provider_b" {
  description = "The workload identity provider of the encryption key service B."
  type        = string
}

variable "federated_learning_service_account_a" {
  description = "The service account to impersonate of the encryption key service A."
  type        = string
}

variable "federated_learning_service_account_b" {
  description = "The service account to impersonate of the encryption key service B."
  type        = string
}

## Service accounts
variable "federated_learning_confidential_space_aggregator_service_account" {
  description = "Name of the aggregator service account to allowlist in the coordinator"
  type        = string
}

variable "federated_learning_confidential_space_modelupdater_service_account" {
  description = "Name of the model updater service account to allowlist in the coordinator"
  type        = string
}

variable "federated_learning_collector_service_account" {
  description = "Name of the collector service account"
  type        = string
}

variable "federated_learning_task_assignment_service_account" {
  description = "Name of the task assignment service account"
  type        = string
}

variable "federated_learning_task_management_service_account" {
  description = "Name of the task management service account"
  type        = string
}

variable "federated_learning_task_scheduler_service_account" {
  description = "Name of the task scheduler service account"
  type        = string
}

variable "federated_learning_task_builder_service_account" {
  description = "Name of the task builder service account"
  type        = string
}

## Container images
variable "federated_learning_aggregator_image" {
  description = "The container image for aggregator"
  type        = string
}

variable "federated_learning_modelupdater_image" {
  description = "The container image for model updater"
  type        = string
}

variable "federated_learning_collector_image" {
  description = "The container image for collector"
  type        = string
}

variable "federated_learning_task_assignment_image" {
  description = "The container image for task assignment"
  type        = string
}

variable "federated_learning_task_management_image" {
  description = "The container image for task management"
  type        = string
}

variable "federated_learning_task_scheduler_image" {
  description = "The container image for task scheduler"
  type        = string
}

variable "federated_learning_task_builder_image" {
  description = "The container image for task builder"
  type        = string
}

## Misc
variable "federated_learning_download_plan_token_duration" {
  description = "Duration in seconds the download plan signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_download_checkpoint_token_duration" {
  description = "Duration in seconds the download checkpoint signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_upload_gradient_token_duration" {
  description = "Duration in seconds the upload gradient signed URL token is valid for"
  type        = number
  default     = 900
}

variable "federated_learning_allow_rooted_devices" {
  description = "Whether to allow rooted devices. This setting will have no effect when authentication is disabled. It is recommended to be set false for production environments."
  type        = bool
  default     = false
}

variable "federated_learning_is_authentication_enabled" {
  description = "Whether to enable authentication"
  type        = bool
  default     = false
}

variable "federated_learning_local_compute_timeout_minutes" {
  description = "The duration an assignment will remain in ASSIGNED status before timing out in minutes."
  type        = number
  default     = 15
}

variable "federated_learning_upload_timeout_minutes" {
  description = "The duration an assignment will remain in LOCAL_COMPLETED status before timing out in minutes."
  type        = number
  default     = 15
}

variable "federated_learning_aggregation_batch_failure_threshold" {
  description = "The number of aggregation batches failed for an iteration before moving the iteration to a failure state."
  type        = number
  default     = 3
}

variable "federated_learning_collector_batch_size" {
  description = "The size of aggregation batches created by the collector"
  type        = number
  default     = 50
}
