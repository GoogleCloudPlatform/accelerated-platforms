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

#
# Configuration dependencies
# - shared_config/platform_variables.tf
#

locals {
  kaggle_api_token_secret_manager_secret_name       = var.kaggle_api_token_secret_manager_secret_name != null ? var.kaggle_api_token_secret_manager_secret_name : "${local.unique_identifier_prefix}-kaggle-api-token"
  kaggle_bucket_location                            = var.kaggle_bucket_location != null ? var.kaggle_bucket_location : var.platform_default_region
  kaggle_bucket_name                                = var.kaggle_bucket_name != null ? var.kaggle_bucket_name : "${local.unique_identifier_prefix}-kaggle-${local.kaggle_bucket_project_id}"
  kaggle_bucket_project_id                          = var.kaggle_bucket_project_id != null ? var.kaggle_bucket_project_id : var.platform_default_project_id
  kaggle_downloader_service_account_email           = "${local.kaggle_downloader_service_account_name}@${local.kaggle_downloader_service_account_project_id}.iam.gserviceaccount.com"
  kaggle_downloader_service_account_id              = "projects/${local.kaggle_downloader_service_account_project_id}/serviceAccounts/${local.kaggle_downloader_service_account_email}"
  kaggle_downloader_service_account_name            = var.kaggle_downloader_service_account_name != null ? var.kaggle_downloader_service_account_name : "${local.unique_identifier_prefix}-kaggle-dl"
  kaggle_downloader_service_account_project_id      = var.kaggle_downloader_service_account_project_id != null ? var.kaggle_downloader_service_account_project_id : var.platform_default_project_id
  kaggle_downloader_kubernetes_namespace_name       = var.kaggle_downloader_kubernetes_namespace_name != null ? var.kaggle_downloader_kubernetes_namespace_name : "${local.unique_identifier_prefix}-kaggle-downloader"
  kaggle_downloader_kubernetes_service_account_name = var.kaggle_downloader_kubernetes_service_account_name != null ? var.kaggle_downloader_kubernetes_service_account_name : "${local.unique_identifier_prefix}-kaggle-downloader"
  kaggle_secret_manager_project_id                  = var.kaggle_secret_manager_project_id != null ? var.kaggle_secret_manager_project_id : var.platform_default_project_id
}

variable "kaggle_api_token_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the Kaggle API token."
  type        = string
}

variable "kaggle_bucket_location" {
  default     = null
  description = "The location of the Kaggle bucket."
  type        = string
}

variable "kaggle_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store Kaggle artifacts."
  type        = string
}

variable "kaggle_bucket_project_id" {
  default     = null
  description = "The project ID for the Kaggle artifacts bucket."
  type        = string
}

variable "kaggle_downloader_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the Kaggle downloader."
  type        = string
}

variable "kaggle_downloader_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the Kaggle downloader."
  type        = string
}

variable "kaggle_downloader_service_account_name" {
  default     = null
  description = "The name of the Kaggle downloader Google Cloud service account."
  type        = string
}

variable "kaggle_downloader_service_account_project_id" {
  default     = null
  description = "The project ID of the Kaggle downloader Google Cloud service account."
  type        = string
}

variable "kaggle_secret_manager_project_id" {
  default     = null
  description = "The project ID of the Secret Manager project containing the Kaggle secrets."
  type        = string
}
