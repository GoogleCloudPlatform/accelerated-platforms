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

##################################################################################
# UNIQUE VALUES
##################################################################################
#
# Cloud storage bucket names have to be globally unique and have a maximum 
# length of 63 characters. When creating bucket names, using the following 
# convention can help ensure they are globally unique:
#   <unique_identifier_prefix>-<unique_tag>-<project_id>
#               13      +     1   +  18 +  1  +  30      = 63
#   
# - <unique_identifier_prefix> is "<platform_resource_name_prefix>-<platform_name>"
#     with a maximum of 13 characters.
# - <project_id> is a maximum of 30.
# - This leaves a maximum of 20, characters for <unique_tag>. Preferable 
#     18 characters with a hyphen before and after.
#
##################################################################################

locals {
  terraform_bucket_name = var.terraform_bucket_name != null ? var.terraform_bucket_name : "${local.unique_identifier_prefix}-terraform-${local.terraform_project_id}"
  terraform_project_id  = var.terraform_project_id != null ? var.terraform_project_id : var.platform_default_project_id

  unique_identifier_prefix            = "${var.platform_resource_name_prefix}-${var.platform_name}"
  unique_identifier_prefix_underscore = replace("${var.platform_resource_name_prefix}-${var.platform_name}", "-", "_")
}

variable "platform_custom_role_unique_suffix" {
  default     = "null"
  description = "Unique suffix for custom roles"
  type        = string
}

variable "platform_default_location" {
  default     = "us-central1"
  description = "Default location for creating resources."
  type        = string
}

variable "platform_default_project_id" {
  description = "The default project ID to use if a more specific project ID is not specified."
  type        = string

  validation {
    condition     = var.platform_default_project_id != ""
    error_message = "'platform_default_project_id' was not set, please set the value in 'shared_config/platform.auto.tfvars' file or via the TF_VAR_platform_default_project_id"
  }
}

variable "platform_name" {
  default     = "dev"
  description = "Name of the environment."
  type        = string

  validation {
    condition     = length(var.platform_name) >= 1 && length(var.platform_name) <= 9
    error_message = "platform_name must be 1 - 9 characters."
  }
}

variable "platform_resource_name_prefix" {
  default     = "acp"
  description = "The prefix to add before each resource's name."
  type        = string

  validation {
    condition     = length(var.platform_resource_name_prefix) >= 1 && length(var.platform_resource_name_prefix) <= 3
    error_message = "platform_resource_name_prefix must be 1 - 3 characters."
  }
}

variable "terraform_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket to use for Terraform."
  type        = string
}

variable "terraform_project_id" {
  default     = null
  description = "The project ID of Terraform bucker."
  type        = string
}

variable "terraform_write_tfvars" {
  default     = true
  description = "Write the configured values to the tfvars configuration files."
  type        = bool
}
