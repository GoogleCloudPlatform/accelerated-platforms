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
  workstation_cluster_name                       = var.workstation_cluster_name != null ? var.workstation_cluster_name : local.unique_identifier_prefix
  workstation_cluster_project_id                 = var.workstation_cluster_project_id != null ? var.workstation_cluster_project_id : var.platform_default_project_id
  workstation_cluster_region                     = var.workstation_cluster_region != null ? var.workstation_cluster_region : var.platform_default_location
  workstation_cluster_service_account_id         = var.workstation_cluster_service_account_id != null ? var.workstation_cluster_service_account_id : "vm-cws-${local.unique_identifier_prefix}"
  workstation_cluster_service_account_project_id = var.workstation_cluster_service_account_project_id != null ? var.workstation_cluster_service_account_project_id : local.workstation_cluster_project_id
}

variable "workstation_cluster_name" {
  default     = null
  description = "The name of the Cloud Workstations cluster."
  type        = string
}

variable "workstation_cluster_project_id" {
  default     = null
  description = "The project ID for the Cloud Workstations cluster."
  type        = string
}

variable "workstation_cluster_region" {
  default     = null
  description = "The region of Cloud Workstations cluster."
  type        = string
}

variable "workstation_cluster_service_account_id" {
  default     = null
  description = "The name of the Google service account for the Cloud Workstations cluster."
  type        = string
}

variable "workstation_cluster_service_account_project_id" {
  default     = null
  description = "The project ID of the Google service account for the Cloud Workstations cluster."
  type        = string
}
