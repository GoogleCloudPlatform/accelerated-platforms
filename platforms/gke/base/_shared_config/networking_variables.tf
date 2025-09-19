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
  network_cluster_network_name             = var.network_cluster_network_name != null ? var.network_cluster_network_name : local.unique_identifier_prefix
  network_cluster_network_nat_gateway_name = var.network_cluster_network_nat_gateway_name != null ? var.network_cluster_network_nat_gateway_name : local.unique_identifier_prefix
  network_cluster_network_router_name      = var.network_cluster_network_router_name != null ? var.network_cluster_network_router_name : local.unique_identifier_prefix
  network_cluster_subnet_node_name         = var.network_cluster_subnet_node_name != null ? var.network_cluster_subnet_node_name : local.unique_identifier_prefix
  network_cluster_subnet_proxy_name        = var.network_cluster_subnet_proxy_name != null ? var.network_cluster_subnet_proxy_name : "${local.unique_identifier_prefix}-proxy"
}

variable "network_cluster_network_dynamic_routing_mode" {
  default     = "GLOBAL"
  description = "VPC network dynamic routing mode."
  type        = string
}

variable "network_cluster_network_name" {
  default     = null
  description = "Name of the VPC network."
  type        = string
}

variable "network_cluster_network_nat_gateway_name" {
  default     = null
  description = "Name of the Cloud NAT Gateway."
  type        = string
}

variable "network_cluster_network_router_name" {
  default     = null
  description = "Name of the Cloud Router."
  type        = string
}

variable "network_cluster_subnet_master_ipv4_cidr_block" {
  default     = "172.16.0.32/28"
  description = "The IP range in CIDR notation to use for the hosted master network. This range will be used for assigning private IP addresses to the cluster master(s) and the ILB VIP. This range must not overlap with any other ranges in use within the cluster's network, and it must be a /28 subnet."
  type        = string
}

variable "network_cluster_subnet_node_ip_cidr_range" {
  default     = "10.128.0.0/20"
  description = "IP CIDR range for the regional node subnet."
  type        = string
}

variable "network_cluster_subnet_node_name" {
  default     = null
  description = "Name of the regional node subnet."
  type        = string
}

variable "network_cluster_subnet_proxy_ip_cidr_range" {
  default     = "10.128.16.0/23"
  description = "IP CIDR range for the regional proxy subnet."
  type        = string
}

variable "network_cluster_subnet_proxy_name" {
  default     = null
  description = "Name of the regional proxy subnet."
  type        = string
}
