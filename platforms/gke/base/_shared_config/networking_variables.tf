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

variable "network_cluster_subnet_node_ip_cidr_range" {
  default = {
    "africa-south1"           = "10.218.0.0/20"
    "asia-east1"              = "10.140.0.0/20"
    "asia-east2"              = "10.170.0.0/20"
    "asia-northeast1"         = "10.146.0.0/20"
    "asia-northeast2"         = "10.174.0.0/20"
    "asia-northeast3"         = "10.178.0.0/20"
    "asia-south1"             = "10.160.0.0/20"
    "asia-south2"             = "10.190.0.0/20"
    "asia-southeast1"         = "10.148.0.0/20"
    "asia-southeast2"         = "10.184.0.0/20"
    "australia-southeast1"    = "10.152.0.0/20"
    "australia-southeast2"    = "10.192.0.0/20"
    "europe-central2"         = "10.186.0.0/20"
    "europe-north1"           = "10.166.0.0/20"
    "europe-north2"           = "10.226.0.0/20"
    "europe-southwest1"       = "10.204.0.0/20"
    "europe-west1"            = "10.132.0.0/20"
    "europe-west10"           = "10.214.0.0/20"
    "europe-west12"           = "10.210.0.0/20"
    "europe-west2"            = "10.154.0.0/20"
    "europe-west3"            = "10.156.0.0/20"
    "europe-west4"            = "10.164.0.0/20"
    "europe-west6"            = "10.172.0.0/20"
    "europe-west8"            = "10.198.0.0/20"
    "europe-west9"            = "10.200.0.0/20"
    "me-central1"             = "10.212.0.0/20"
    "me-west1"                = "10.208.0.0/20"
    "northamerica-northeast1" = "10.162.0.0/20"
    "northamerica-northeast2" = "10.188.0.0/20"
    "northamerica-south1"     = "10.224.0.0/20"
    "southamerica-east1"      = "10.158.0.0/20"
    "southamerica-west1"      = "10.194.0.0/20"
    "us-central1"             = "10.128.0.0/20"
    "us-east1"                = "10.142.0.0/20"
    "us-east4"                = "10.150.0.0/20"
    "us-east5"                = "10.202.0.0/20"
    "us-south1"               = "10.206.0.0/20"
    "us-west1"                = "10.138.0.0/20"
    "us-west2"                = "10.168.0.0/20"
    "us-west3"                = "10.180.0.0/20"
    "us-west4"                = "10.182.0.0/20"
  }
  description = "Cluster node subnet region to IP CIDR range mapping"
  type        = map(string)
}

variable "network_cluster_subnet_node_name" {
  default     = null
  description = "Name of the regional node subnet."
  type        = string
}

variable "network_cluster_subnet_proxy_ip_cidr_range" {
  default = {
    "africa-south1"           = "###.###.0.0/23"
    "asia-east1"              = "###.###.0.0/23"
    "asia-east2"              = "###.###.0.0/23"
    "asia-northeast1"         = "###.###.0.0/23"
    "asia-northeast2"         = "###.###.0.0/23"
    "asia-northeast3"         = "###.###.0.0/23"
    "asia-south1"             = "###.###.0.0/23"
    "asia-south2"             = "###.###.0.0/23"
    "asia-southeast1"         = "###.###.0.0/23"
    "asia-southeast2"         = "###.###.0.0/23"
    "australia-southeast1"    = "###.###.0.0/23"
    "australia-southeast2"    = "###.###.0.0/23"
    "europe-central2"         = "###.###.0.0/23"
    "europe-north1"           = "###.###.0.0/23"
    "europe-north2"           = "###.###.0.0/23"
    "europe-southwest1"       = "###.###.0.0/23"
    "europe-west1"            = "###.###.0.0/23"
    "europe-west10"           = "###.###.0.0/23"
    "europe-west12"           = "###.###.0.0/23"
    "europe-west2"            = "###.###.0.0/23"
    "europe-west3"            = "###.###.0.0/23"
    "europe-west4"            = "###.###.0.0/23"
    "europe-west6"            = "###.###.0.0/23"
    "europe-west8"            = "###.###.0.0/23"
    "europe-west9"            = "###.###.0.0/23"
    "me-central1"             = "###.###.0.0/23"
    "me-west1"                = "###.###.0.0/23"
    "northamerica-northeast1" = "###.###.0.0/23"
    "northamerica-northeast2" = "###.###.0.0/23"
    "northamerica-south1"     = "###.###.0.0/23"
    "southamerica-east1"      = "###.###.0.0/23"
    "southamerica-west1"      = "###.###.0.0/23"
    "us-central1"             = "10.128.16.0/23"
    "us-east1"                = "###.###.0.0/23"
    "us-east4"                = "###.###.0.0/23"
    "us-east5"                = "###.###.0.0/23"
    "us-south1"               = "###.###.0.0/23"
    "us-west1"                = "###.###.0.0/23"
    "us-west2"                = "###.###.0.0/23"
    "us-west3"                = "###.###.0.0/23"
    "us-west4"                = "###.###.0.0/23"
  }
  description = "Cluster proxy-only subnet region to IP CIDR range mapping. A /26 or larger range is required, /23 is recommended."
  type        = map(string)
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
