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

variable "federated_learning_nvidia_flare_tff_example_bucket_name" {
  description = "Cloud Storage bucket name to store the NVIDIA FLARE example workspace"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_container_image_tag" {
  description = "Container image tag of the NVIDIA FLARE container image to deploy"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_domain" {
  default     = "nvidia-flare-example.com"
  description = "Domain to use to build the FQDN for NVIDIA FLARE clients and servers"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_localized_container_image_id" {
  description = "Container image id (localized with the repository) of the NVIDIA FLARE container image to deploy"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_tenant_name" {
  description = "Name of the tenant where to deploy NVIDIA FLARE workloads"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_workload_to_deploy" {
  description = "NVIDIA FLARE workload to deploy in the cluster."
  type        = string

  validation {
    condition     = var.federated_learning_nvidia_flare_tff_example_workload_to_deploy == "server1"
    error_message = "Valid values are: client1, client2, server1"
  }
}
