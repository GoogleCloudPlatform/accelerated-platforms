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

locals {
  unique_identifier_prefix = "${var.resource_name_prefix}-${var.platform_name}"
}

variable "platform_name" {
  default     = "dev"
  description = "Name of the environment"
  type        = string
}

variable "resource_name_prefix" {
  default     = "acp"
  description = "The prefix to add before each resource's name"
  type        = string
}
