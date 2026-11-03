# Copyright 2026 Google LLC
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

variable "backend_ports" {
  default     = ["8000", "8081", "19001"]
  description = "Ports that load balancer proxies and health checks must reach: vLLM (8000), llm-d router proxy (8081) and its readiness listener (19001)."
  type        = list(string)
}

variable "network_name" {
  description = "Name of the shared VPC network."
  type        = string
}

variable "project_id" {
  description = "Fleet host project. Every regional cluster must be in this project."
  type        = string
}

variable "regions" {
  description = "Regions keyed by region key, with their non-overlapping CIDR ranges."
  type = map(object({
    region              = string
    node_cidr           = string
    regional_proxy_cidr = string
    global_proxy_cidr   = string
  }))
}

output "network_id" {
  value = google_compute_network.vpc.id
}

output "network_name" {
  value = google_compute_network.vpc.name
}

output "global_proxy_subnets" {
  value = { for k, s in google_compute_subnetwork.global_proxy : k => s.name }
}
