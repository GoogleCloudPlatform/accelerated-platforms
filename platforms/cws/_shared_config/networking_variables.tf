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
  cws_nat_gateway_name = var.cws_nat_gateway_name != null ? var.cws_nat_gateway_name : "${local.unique_identifier_prefix}-cws"
  cws_network_name     = var.cws_network_name != null ? var.cws_network_name : "${local.unique_identifier_prefix}-cws"
  cws_router_name      = var.cws_router_name != null ? var.cws_router_name : "${local.unique_identifier_prefix}-cws"
  cws_subnetwork_name  = var.cws_subnetwork_name != null ? var.cws_subnetwork_name : "${local.unique_identifier_prefix}-cws"
}

variable "cws_nat_gateway_name" {
  default     = null
  description = "Name of the Cloud NAT Gateway."
  type        = string
}

variable "cws_network_name" {
  default     = null
  description = "Name of the VPC network."
  type        = string
}

variable "cws_network_routing_mode" {
  default     = "GLOBAL"
  description = "VPC dynamic routing mode."
  type        = string
}

variable "cws_router_name" {
  default     = null
  description = "Name of the Cloud Router."
  type        = string
}

variable "cws_subnetwork_ip_cidr_range" {
  default     = "10.40.0.0/22"
  description = "CIDR range for the regional subnet."
  type        = string
}

variable "cws_subnetwork_name" {
  default     = null
  description = "Name of the regional subnet."
  type        = string
}
