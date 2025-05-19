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

variable "app_name" {
  default = null
  type    = string
}

variable "accelerator" {
  default = null
  type    = string
}

variable "artifact_repo_name" {
  default = null
  type    = string
}

variable "comfyui_kubernetes_namespace" {
  default = null
  type    = string
}

variable "comfyui_image_name" {
  default = null
  type    = string
}

variable "comfyui_image_staging_bucket" {
  default = null
  type    = string
}

variable "comfyui_image_tag" {
  default = null
  type    = string
}

variable "comfyui_storage_buckets" {
  default     = {}
  description = "Map describing the Cloud Storage buckets to create. Keys are bucket names."
  type = map(object({
    force_destroy      = bool
    versioning_enabled = bool
  }))
}

variable "iap_domain" {
  default = null
  type    = string
}







