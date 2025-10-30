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
  cws_comfyui_model_bucket_location   = var.cws_comfyui_model_bucket_location != null ? var.cws_comfyui_model_bucket_location : var.platform_default_location
  cws_comfyui_model_bucket_name       = var.cws_comfyui_model_bucket_name != null ? var.cws_comfyui_model_bucket_name : "${local.unique_identifier_prefix}-comfyui-models"
  cws_comfyui_model_bucket_project_id = var.cws_comfyui_model_bucket_project_id != null ? var.cws_comfyui_model_bucket_project_id : var.platform_default_project_id
}

variable "cws_comfyui_model_bucket_location" {
  default     = null
  description = "Location of the ComfyUI model bucket."
  type        = string
}

variable "cws_comfyui_model_bucket_name" {
  default     = null
  description = "Name of the ComfyUI model bucket."
  type        = string
}

variable "cws_comfyui_model_bucket_project_id" {
  default     = null
  description = "Project ID of the ComfyUI model bucket."
  type        = string
}
