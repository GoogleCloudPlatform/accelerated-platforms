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

variable "active_backend" {
  description = "Backend (experiment arm) that receives the traffic: a key of var.backends."
  type        = string
}

variable "backends" {
  description = "Experiment arms and their regional standalone NEGs."
  type = map(object({
    health_check_path  = string
    health_check_port  = number
    locality_lb_policy = optional(string, "LEAST_REQUEST")
    negs = list(object({
      region                              = string
      self_link                           = string
      max_rate_per_endpoint               = optional(number)
      max_in_flight_requests_per_endpoint = optional(number)
    }))
  }))
}

variable "load_balancing_algorithm" {
  default     = "WATERFALL_BY_REGION"
  description = "Cross-region traffic distribution: WATERFALL_BY_REGION (locality first, spill over when a region reaches its capacity), SPRAY_TO_REGION (closest region first like WATERFALL_BY_REGION, but each proxy spreads requests across every zone of the region), or WATERFALL_BY_ZONE."
  type        = string

  validation {
    condition     = contains(["WATERFALL_BY_REGION", "SPRAY_TO_REGION", "WATERFALL_BY_ZONE"], var.load_balancing_algorithm)
    error_message = "load_balancing_algorithm must be WATERFALL_BY_REGION, SPRAY_TO_REGION, or WATERFALL_BY_ZONE."
  }
}

variable "name" {
  description = "Name prefix of the load balancer resources."
  type        = string
}

variable "network" {
  description = "Self link or ID of the shared VPC network."
  type        = string
}

variable "preferred_region" {
  default     = ""
  description = "Optional region whose backends are marked PREFERRED: they are used to capacity before any other region."
  type        = string
}

variable "project_id" {
  description = "Project of the load balancer, the network, and the NEGs."
  type        = string
}

variable "regions" {
  description = "Regions that get a VIP, keyed by region key, with the subnetwork for the VIP."
  type = map(object({
    region     = string
    subnetwork = string
  }))
}

variable "timeout_sec" {
  default     = 3600
  description = "Backend service timeout. Long streaming generations need a long timeout."
  type        = number
}

output "vips" {
  description = "Internal VIP per region key."
  value       = { for k, fr in google_compute_global_forwarding_rule.vip : k => fr.ip_address }
}

output "backend_services" {
  value = { for k, bs in google_compute_backend_service.backend : k => bs.name }
}

variable "balancing_mode" {
  description = "How the load balancer measures backend capacity: IN_FLIGHT (in-progress requests per endpoint, with traffic duration LONG; for requests that take more than a second, like LLM completions) or RATE (new requests per second per endpoint)."
  type        = string
  default     = "IN_FLIGHT"

  validation {
    condition     = contains(["IN_FLIGHT", "RATE"], var.balancing_mode)
    error_message = "balancing_mode must be IN_FLIGHT or RATE."
  }
}
