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
# - shared_config/cluster_variables.tf
# - shared_config/platform_variables.tf
#

locals {
  huggingface_hub_access_token_read_secret_manager_secret_name  = var.huggingface_hub_access_token_read_secret_manager_secret_name != null ? var.huggingface_hub_access_token_read_secret_manager_secret_name : "${local.unique_identifier_prefix}-huggingface-hub-access-token-read"
  huggingface_hub_access_token_write_secret_manager_secret_name = var.huggingface_hub_access_token_write_secret_manager_secret_name != null ? var.huggingface_hub_access_token_write_secret_manager_secret_name : "${local.unique_identifier_prefix}-huggingface-hub-access-token-write"
  huggingface_hub_models_bucket_location                        = var.huggingface_hub_models_bucket_location != null ? var.huggingface_hub_models_bucket_location : var.cluster_region
  huggingface_hub_models_bucket_name                            = var.huggingface_hub_models_bucket_name != null ? var.huggingface_hub_models_bucket_name : "${local.huggingface_hub_models_bucket_project_id}-${local.unique_identifier_prefix}-hf-hub-models"
  huggingface_hub_models_bucket_project_id                      = var.huggingface_hub_models_bucket_project_id != null ? var.huggingface_hub_models_bucket_project_id : var.platform_default_project_id
  huggingface_secret_manager_project_id                         = var.huggingface_secret_manager_project_id != null ? var.huggingface_secret_manager_project_id : var.platform_default_project_id
}

variable "huggingface_hub_access_token_read_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the Hugging Face Hub access token with read permissions"
  type        = string
}

variable "huggingface_hub_access_token_write_secret_manager_secret_name" {
  default     = null
  description = "The name of the Secret Manager secret containing the Hugging Face Hub access token with write permissions"
  type        = string
}

variable "huggingface_hub_models_bucket_location" {
  default     = null
  description = "The location of the Hugging Face Hub models bucket."
  type        = string
}

variable "huggingface_hub_models_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store the Hugging Face Hub models."
  type        = string
}

variable "huggingface_hub_models_bucket_project_id" {
  default     = null
  description = "The project ID for the Hugging Face Hub models bucket."
  type        = string
}

variable "huggingface_secret_manager_project_id" {
  default     = null
  description = "The project ID of the Secret Manager project containing the Hugging Face secrets"
  type        = string
}
