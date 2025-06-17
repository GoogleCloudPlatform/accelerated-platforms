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

locals {
  workflow_api_artifact_repo_name = "${local.unique_identifier_prefix}-${var.workflow_api_artifact_repo_name}"
  workflow_api_endpoints_hostname = var.workflow_api_endpoints_hostname != null ? var.workflow_api_endpoints_hostname : "workflow-api.${var.comfyui_kubernetes_namespace}.${local.unique_identifier_prefix}.endpoints.${local.cluster_project_id}.cloud.goog"
}

variable "workflow_api_artifact_repo_name" {
  default = "workflow-api"
  description = ""
  type = string
}

variable "workflow_api_image_name" {
  default = "workflow-api"
  description = ""
  type = string
}

variable "workflow_api_image_tag" {
  default = "0.0.1"
  description = ""
  type = string
}

variable "workflow_api_endpoints_hostname" {
  default = null
  type = string
}

variable "workflow_api_gateway_subnet_cidr_range" {
  default = "172.18.0.0/26"
  type = string
}

variable "workflow_api_proxy_subnet_cidr_range" {
  default = "172.19.0.0/26"
  type = string
}

variable "network_name" {
  default     = null
  description = "Name of the VPC network"
  type        = string
}
