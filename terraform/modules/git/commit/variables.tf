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

variable "commit_message" {
  description = ""
  type        = string
}

variable "content_hash" {
  default     = null
  description = ""
  type        = string
}

variable "directory_to_commit" {
  description = ""
  type        = string
}

variable "git_provider" {
  description = ""
  type        = string
}

variable "lock_timeout" {
  default     = "30s"
  description = "Timeout duration is a floating point number with an optional suffix.: 's' for seconds (the default), 'm' for minutes, 'h' for hours or 'd' for days. A duration of 0 disables the associated timeout."
  type        = string
}

variable "namespace" {
  description = ""
  type        = string
}

variable "repository" {
  description = ""
  type        = string
}

variable "temporary_directory" {
  description = ""
  type        = string
}

variable "secret_manager_secret_version" {
  description = ""
  type        = any
}
