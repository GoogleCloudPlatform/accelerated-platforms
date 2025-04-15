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

variable "initialize_backend_use_case_name" {
  default     = null
  description = "Create a templated backend.tf file in each folder that contains a versions.tf file for the specified use case. This value should be a folder or path within the 'base/use-cases' directory."
  type        = string
}

variable "initialize_container_node_pools_cpu" {
  default     = true
  description = "Set to true to prepare the files to provision CPU-based node pools in the cluster region"
  type        = bool
}

variable "initialize_container_node_pools_gpu" {
  default     = true
  description = "Set to true to prepare the files to provision GPU-based node pools in the cluster region"
  type        = bool
}

variable "initialize_container_node_pools_tpu" {
  default     = true
  description = "Set to true to prepare the files to provision TPU-based node pools in the cluster region"
  type        = bool
}
