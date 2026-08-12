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

variable "storage_class_rwx_default" {
  default     = true
  description = "Make the ReadWriteMany StorageClass the cluster default. Workloads that request a ReadWriteMany volume without naming a StorageClass (llm-d-benchmark, for example) get a Persistent Disk otherwise, and Persistent Disk cannot provision ReadWriteMany."
  type        = bool
}

variable "storage_class_rwx_filestore_tier" {
  default     = "standard"
  description = "The Filestore service tier backing the ReadWriteMany StorageClass."
  type        = string

  validation {
    condition = contains(
      [
        "enterprise",
        "premium",
        "standard",
        "zonal",
      ],
      var.storage_class_rwx_filestore_tier
    )
    error_message = "'storage_class_rwx_filestore_tier' value is invalid"
  }
}

variable "storage_class_rwx_name" {
  default     = null
  description = "The name of the ReadWriteMany StorageClass. Defaults to '<resource_name_prefix>-<platform_name>-rwx'."
  type        = string
}
