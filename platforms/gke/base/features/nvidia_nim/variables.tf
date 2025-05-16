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

variable "nvidia_ncg_api_key_secret_manager_project_id" {
  description = "description"
  type        = string
}

variable "nvidia_ncg_api_key_secret_manager_secret_name" {
  description = "description"
  type        = string
}

variable "nvidia_nim_llm_name" {
  description = "description"
  type        = any
}

variable "nvidia_nim_llm_helm_chart_values" {
  description = "description"
  type        = any
}

variable "nvidia_nim_llm_helm_chart_version" {
  default     = "1.7.0"
  description = "description"
  type        = string
}

