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
  description = "Ports that load balancer proxies and health checks must reach on the backends: OpenAI-compatible model servers and frontends such as vLLM, TensorRT-LLM, and NVIDIA Dynamo (8000), and the llm-d router proxy (8081) and its readiness listener (19001)."
  type        = list(string)
}

variable "network_name" {
  description = "Name of the VPC network shared by every regional platform."
  type        = string
}

variable "project_id" {
  description = "Project of the network and of every regional platform."
  type        = string
}

variable "regions" {
  description = "Regional platforms of the environment, keyed by platform name, with their region and non-overlapping CIDR ranges (computed by mr_set_cidrs_for_index in helpers.sh)."
  type = map(object({
    global_proxy_cidr   = string
    node_cidr           = string
    pod_cidr            = string
    region              = string
    regional_proxy_cidr = string
  }))

  validation {
    condition     = length(distinct([for r in values(var.regions) : r.region])) == length(var.regions)
    error_message = "Each region can have only one platform: a VPC network has a single active proxy-only subnet per purpose in each region."
  }

  validation {
    condition = alltrue(flatten([
      for r in values(var.regions) : [
        for cidr in [r.global_proxy_cidr, r.node_cidr, r.pod_cidr, r.regional_proxy_cidr] : can(cidrhost(cidr, 0))
      ]
    ]))
    error_message = "Every CIDR range in regions must be a valid IPv4 CIDR block."
  }
}
