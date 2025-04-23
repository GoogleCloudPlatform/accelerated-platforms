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

variable "ira_cloud_storage_buckets" {
  default     = {}
  description = "Map describing the Cloud Storage buckets to create. Keys are bucket names."
  type = map(object({
    force_destroy      = bool
    versioning_enabled = bool
  }))
}

variable "ira_cloud_storage_buckets_iam_bindings" {
  default     = []
  description = "Map of objects to configure Cloud IAM bindings for Cloud Storage buckets described by the ira_cloud_storage_buckets variable. Keys are bucket names. Use the same names that you use in the ira_cloud_storage_buckets variable"
  type = list(object({
    bucket_name = string
    member      = string
    role        = string
  }))
}

variable "ira_use_case_flavor" {
  default = ""
  type    = string

  validation {
    condition = var.ira_use_case_flavor == "" || contains(
      [
        "ira-online-gpu",
      ],
      var.ira_use_case_flavor
    )
    error_message = "'ira_use_case_flavor' value is invalid"
  }
}

variable "ira_kubernetes_namespace" {
  default = "default"
  type    = string
}
