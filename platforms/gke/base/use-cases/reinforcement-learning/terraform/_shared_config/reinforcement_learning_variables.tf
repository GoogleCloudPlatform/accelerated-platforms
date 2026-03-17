# Copyright 2026 Google LLC
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
  rl_dataset_bucket_name                      = var.rl_dataset_bucket_name != null ? var.rl_dataset_bucket_name : "${local.rl_project_id}-${local.unique_identifier_prefix}-dataset"
  rl_kubernetes_namespace_manifests_directory = "${path.module}/manifests/${local.rl_kubernetes_namespace}"
  rl_kubernetes_namespace                     = var.rl_kubernetes_namespace != null ? var.rl_kubernetes_namespace : "${local.unique_identifier_prefix}-rl"
  rl_kubernetes_service_account_name          = var.rl_kubernetes_service_account_name != null ? var.rl_kubernetes_service_account_name : "${local.unique_identifier_prefix}-rl-sa"
  rl_mlflow_data_bucket_name                  = var.rl_mlflow_data_bucket_name != null ? var.rl_mlflow_data_bucket_name : "${local.rl_project_id}-${local.unique_identifier_prefix}-mlflow-data"
  rl_project_id                               = var.rl_project_id != null ? var.rl_project_id : var.platform_default_project_id

  rl_cpu_reinforcement_learning_dataset_downloader_image_url = var.rl_cpu_reinforcement_learning_dataset_downloader_image_url != null ? var.rl_cpu_reinforcement_learning_dataset_downloader_image_url : "${local.cloudbuild_ar_image_repository_url}/reinforcement-learning/rl-dataset-downloader:latest"
  rl_tpu_reinforcement_learning_on_tpu_image_url             = var.rl_tpu_reinforcement_learning_on_tpu_image_url != null ? var.rl_tpu_reinforcement_learning_on_tpu_image_url : "${local.cloudbuild_ar_image_repository_url}/reinforcement-learning/rl-on-tpu:latest"

  rl_kubernetes_service_accounts = {
    mlflow = {
      automount_service_account_token = false
      service_account_name            = "${local.rl_kubernetes_service_account_name}"
    }
  }
}

variable "rl_dataset_bucket_name" {
  default     = null
  description = "The GCP bucket name for the RL dataset."
  type        = string
}

variable "rl_kubernetes_namespace" {
  default     = null
  description = "The Kubernetes namespace for the RL on TPU resources."
  type        = string
}

variable "rl_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account name for the RL on TPU resources."
  type        = string
}

variable "rl_mlflow_data_bucket_name" {
  default     = null
  description = "The GCP bucket name for the MLflow data."
  type        = string
}

variable "rl_project_id" {
  default     = null
  description = "The GCP project ID for the RL on TPU resources."
  type        = string
}

variable "rl_cpu_reinforcement_learning_dataset_downloader_image_url" {
  default     = null
  description = "The URL for the RL dataset downloader container image."
  type        = string
}

variable "rl_tpu_reinforcement_learning_on_tpu_image_url" {
  default     = null
  description = "The URL for the RL on TPU container image."
  type        = string
}
