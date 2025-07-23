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

#
# Configuration dependencies
# - shared_config/platform_variables.tf
#

locals {
  nvidia_ncg_api_key_secret_manager_project_id  = var.nvidia_ncg_api_key_secret_manager_project_id != null ? var.nvidia_ncg_api_key_secret_manager_project_id : local.cluster_project_id
  nvidia_ncg_api_key_secret_manager_secret_name = var.nvidia_ncg_api_key_secret_manager_secret_name != null ? var.nvidia_ncg_api_key_secret_manager_secret_name : "${local.unique_identifier_prefix}-nvidia-ncg-api-key"

  nvidia_nim_model_store_bucket_location   = var.nvidia_nim_model_store_bucket_location != null ? var.nvidia_nim_model_store_bucket_location : var.cluster_region
  nvidia_nim_model_store_bucket_name       = var.nvidia_nim_model_store_bucket_name != null ? var.nvidia_nim_model_store_bucket_name : "${local.unique_identifier_prefix}-nvidia-nim-models-${local.nvidia_nim_model_store_bucket_project_id}"
  nvidia_nim_model_store_bucket_project_id = var.nvidia_nim_model_store_bucket_project_id != null ? var.nvidia_nim_model_store_bucket_project_id : local.cluster_project_id
}

variable "nvidia_ncg_api_key_secret_manager_project_id" {
  default     = null
  description = "The project ID of the Secret Manager project containing the NCG API key secret"
  type        = string
}

variable "nvidia_ncg_api_key_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the NCG API key"
  type        = string
}

variable "nvidia_nim_model_store_bucket_location" {
  default     = null
  description = "The location of the NVIDIA NIM models bucket."
  type        = string
}

variable "nvidia_nim_model_store_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store the NVIDIA NIM models."
  type        = string
}

variable "nvidia_nim_model_store_bucket_project_id" {
  default     = null
  description = "The project ID for the NVIDIA NIM models bucket."
  type        = string
}
