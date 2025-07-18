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
  workflow_api_artifact_repo_name             = "${local.unique_identifier_prefix}-${var.workflow_api_artifact_repo_name}"
  workflow_api_default_name                   = "workflow-api"
  workflow_api_endpoints_hostname             = var.workflow_api_endpoints_hostname != null ? var.workflow_api_endpoints_hostname : "${local.workflow_api_default_name}.${var.comfyui_kubernetes_namespace}.${local.unique_identifier_prefix}.endpoints.${local.cluster_project_id}.cloud.goog"
  workflow_api_endpoints_ssl_certificate_name = "${local.unique_identifier_prefix}-${var.comfyui_kubernetes_namespace}-${local.workflow_api_default_name}"
  workflow_api_gateway_address_name           = "${local.unique_identifier_prefix}-${local.workflow_api_default_name}-external-gateway-https"
  workflow_api_gateway_name                   = "${local.workflow_api_default_name}-external-https"

  workflow_api_service_account_email              = "${local.workflow_api_service_account_name}@${local.workflow_api_service_account_project_id}.iam.gserviceaccount.com"
  workflow_api_service_account_name               = "${local.unique_identifier_prefix}-${local.workflow_api_default_name}"
  workflow_api_service_account_oauth_display_name = "${local.unique_identifier_prefix}-${local.workflow_api_default_name}"
  workflow_api_service_account_project_id         = var.workflow_api_service_account_project_id != null ? var.workflow_api_service_account_project_id : var.platform_default_project_id
}

variable "workflow_api_artifact_repo_name" {
  default     = "workflow-api"
  description = ""
  type        = string
}

variable "workflow_api_endpoints_hostname" {
  default     = null
  description = ""
  type        = string
}

variable "workflow_api_image_name" {
  default     = "workflow-api"
  description = ""
  type        = string
}

variable "workflow_api_image_tag" {
  default     = "0.0.1"
  description = ""
  type        = string
}

variable "workflow_api_service_account_project_id" {
  default     = null
  description = ""
  type        = string
}

variable "workflow_api_subnet_gateway_cidr_range" {
  default = "172.18.0.0/26"
  type    = string
}

variable "workflow_api_subnet_proxy_cidr_range" {
  default = "172.19.0.0/26"
  type    = string
}
