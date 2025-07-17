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
  cloudbuild_github_access_token_read_secret_manager_secret_name  = var.cloudbuild_github_access_token_read_secret_manager_secret_name != null ? var.cloudbuild_github_access_token_read_secret_manager_secret_name : "${local.unique_identifier_prefix}-github-access-token-read"
  cloudbuild_github_access_token_write_secret_manager_secret_name = var.cloudbuild_github_access_token_write_secret_manager_secret_name != null ? var.cloudbuild_github_access_token_write_secret_manager_secret_name : "${local.unique_identifier_prefix}-github-access-token-write"
  cloudbuild_location                                             = var.cloudbuild_location != null ? var.cloudbuild_location : var.cluster_region
  cloudbuild_project_id                                           = var.cloudbuild_project_id != null ? var.cloudbuild_project_id : var.platform_default_project_id
  cloudbuild_service_account_email                                = "${local.cloudbuild_service_account_name}@${local.cloudbuild_project_id}.iam.gserviceaccount.com"
  cloudbuild_service_account_id                                   = "projects/${local.cloudbuild_project_id}/serviceAccounts/${local.cloudbuild_service_account_email}"
  cloudbuild_service_account_name                                 = var.cloudbuild_service_account_name != null ? var.cloudbuild_service_account_name : "${local.unique_identifier_prefix}-cloudbuild"
  cloudbuild_source_bucket_name                                   = var.cloudbuild_source_bucket_name != null ? var.cloudbuild_source_bucket_name : "${local.unique_identifier_prefix}-gcb-src-${local.cloudbuild_project_id}"
}

variable "cloudbuild_github_access_token_read_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the GitHub access token with read permissions."
  type        = string
}

variable "cloudbuild_github_access_token_write_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the GitHub access token with write permissions."
  type        = string
}

variable "cloudbuild_location" {
  default     = null
  description = "The default location to create Cloud Build resources."
  type        = string
}

variable "cloudbuild_project_id" {
  default     = null
  description = "The project ID of the Cloud Build project."
  type        = string
}

variable "cloudbuild_service_account_name" {
  default     = null
  description = "The name of the Cloud Build Google Cloud service account."
  type        = string
}

variable "cloudbuild_source_bucket_name" {
  default     = null
  description = "The name of the Cloud Build source bucket."
  type        = string
}
