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

#
# Configuration dependencies
# - shared_config/cluster_variables.tf
# - shared_config/platform_variables.tf

locals {
  iap_project_id = var.iap_project_id != null ? var.iap_project_id : var.cluster_project_id
}

variable "iap_domain" {
  default     = null
  description = "Allowed domain for IAP. An internal user type audience is to limited to authorization requests for members of the organization. For more information see https://support.google.com/cloud/answer/15549945"
  type        = string
}

variable "iap_project_id" {
  default     = null
  description = "Project ID of IAP brand."
  type        = string
}
