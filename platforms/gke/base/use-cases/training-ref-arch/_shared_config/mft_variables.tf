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

# Configuration dependencies
# - shared_config/platform_variables.tf

locals {
  mft_ar_repository_id  = "${local.unique_identifier_prefix}-fine-tuning"
  mft_ar_repository_url = "${local.mft_project_id}-docker.pkg.dev/${local.mft_project_id}/${local.mft_ar_repository_id}"

  mft_bucket_cloudbuild_name = "${local.unique_identifier_prefix}-cloudbuild-${local.mft_project_id}"
  mft_data_bucket_name       = "${local.unique_identifier_prefix}-data-${local.mft_project_id}"
  mft_bucket_model_name      = "${local.unique_identifier_prefix}-model-${local.mft_project_id}"

  mft_namespace  = var.mft_namespace != null ? var.mft_namespace : "${local.unique_identifier_prefix}-mft"
  mft_project_id = var.mft_project_id != null ? var.mft_project_id : var.platform_default_project_id
  mft_region     = var.mft_region != null ? var.mft_region : var.platform_default_region


  iap_project_id = var.iap_project_id != null ? var.iap_project_id : var.platform_default_project_id
}

variable "mft_namespace" {
  default     = null
  description = "The Kubernetes namespace to use for fine-tuning workloads."
  type        = string
}

variable "mft_project_id" {
  default     = null
  description = "The Google Cloud project where the fine-tuning resources will be created."
  type        = string
}

variable "mft_region" {
  default     = null
  description = "The Google Cloud region where the fine-tuning resources will be created."
  type        = string
}

variable "iap_domain" {
  default     = null
  description = "Allowed domain for IAP. An internal user type audience is to limited to authorization requests for members of the organization. For more information see https://support.google.com/cloud/answer/15549945"
  type        = string
}

variable "iap_project_id" {
  default     = null
  description = "Project ID of IAP brand."
  type        = string
}
