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

locals {
  deploy_on_gpu  = contains(["l4", "h100", "h200", "rtx-pro-6000"], var.llmd_accelerator_type) ? true : false
  deploy_on_tpu  = contains(["v6e"], var.llmd_accelerator_type) ? true : false
  llmd_namespace = local.deploy_on_gpu ? local.ira_online_gpu_kubernetes_namespace_name : (local.deploy_on_tpu ? local.ira_online_tpu_kubernetes_namespace_name : "")
}

variable "llmd_accelerator_type" {
  default     = "rtx-pro-6000"
  description = "accelerator type to serve the model on."
  type        = string

  validation {
    condition = contains(
      [
        "h100",
        "h200",
        "rtx-pro-6000",
        "v6e",
      ],
      var.llmd_accelerator_type
    )
    error_message = "'llmd_accelerator_type' value is invalid"
  }
}


variable "llmd_model_id" {
  default     = "qwen/qwen3-32b"
  description = "Id for the model to serve."
  type        = string

  validation {
    condition = contains(
      [
        "google/gemma-4-31b-it",
        "qwen/qwen3-32b",
      ],
      var.llmd_model_id
    )
    error_message = "'llmd_model_id' value is invalid"
  }
}
