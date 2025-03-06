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

variable "federated_learning_nvidia_flare_tff_example_deploy" {
  default     = false
  description = "Set this variable to true to deploy the Federated Learning NVIDIA FLARE TensorFlow example"
  type        = bool
}

variable "federated_learning_nvidia_flare_tff_example_bucket_name" {
  default     = "nvf-ws"
  description = "Cloud Storage bucket name to store the NVIDIA FLARE example workspace"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_container_image_tag" {
  default     = "federated_learning_nvidia_flare_tff_example_container_image_tag_placeholder"
  description = "Container image tag of the NVIDIA FLARE container image to deploy"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_localized_container_image_id" {
  default     = "federated_learning_nvidia_flare_tff_localized_container_image_id_placeholder"
  description = "Container image id (localized with the repository) of the NVIDIA FLARE container image to deploy"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_tenant_name" {
  default     = ""
  description = "Name of the tenant where to deploy NVIDIA FLARE workloads"
  type        = string
}

variable "federated_learning_nvidia_flare_tff_example_workloads_to_deploy" {
  default = [
    "client1",
    "client2",
    "server1"
  ]
  description = "List of the NVIDIA FLARE workloads to deploy in the cluster."
  type        = list(string)

  validation {
    condition     = contains(var.federated_learning_nvidia_flare_tff_example_workloads_to_deploy, "client1") || contains(var.federated_learning_nvidia_flare_tff_example_workloads_to_deploy, "client2") || contains(var.federated_learning_nvidia_flare_tff_example_workloads_to_deploy, "server1")
    error_message = "Valid values are: client1, client2, server1"
  }
}
