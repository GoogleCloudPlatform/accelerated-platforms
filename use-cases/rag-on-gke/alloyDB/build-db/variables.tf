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

variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "region" {
  default     = "us-central1"
  description = "The region for cluster"
  type        = string
}

variable "cluster_name" {
  description = "The name of the cluster"
  type        = string
}

variable "primary_instance_name" {
  description = "The name of the primary instance in the cluster"
  type        = string
  default     = "main"
}

variable "network_name" {
  description = "The ID of the network in which to provision resources."
  type        = string
  default     = "default"
}

variable "alloydb_ip_range" {
  description = "The ip range allocated for alloydb instances"
  type        = string
  default     = "172.16.0.0"
}
variable "alloydb_ip_prefix" {
  description = "The ip prefix used for allocating ip address for alloydb instances"
  type        = number
  default     = 12
}
