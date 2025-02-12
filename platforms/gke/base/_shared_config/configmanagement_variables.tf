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

locals {
  config_management_kubernetes_namespace       = "config-management-system"
  config_management_kubernetes_service_account = "root-reconciler"

  otel_collector_kubernetes_namespace       = "config-management-monitoring"
  otel_collector_kubernetes_service_account = "default"

  git_creds_secret = var.configmanagement_git_credentials.secret_name == null ? "${var.platform_name}-git-creds" : var.configmanagement_git_credentials.secret_name

  oci_repo_id              = "${local.unique_identifier_prefix}-config-sync"
  oci_repo_domain          = "${var.cluster_region}-docker.pkg.dev"
  oci_repo_url             = "${local.oci_repo_domain}/${var.cluster_project_id}/${local.oci_repo_id}"
  oci_root_sync_image      = "${local.oci_root_sync_image_name}:${local.oci_root_sync_image_tag}"
  oci_root_sync_image_name = "root-sync"
  oci_root_sync_image_tag  = "latest"
  oci_sync_repo            = var.configmanagement_sync_repo == null ? local.oci_sync_repo_url : var.configmanagement_sync_repo
  oci_sync_repo_url        = "${local.oci_repo_url}/${local.oci_root_sync_image}"
}

variable "configmanagement_git_credentials" {
  default = {
    secret_name = null
    token       = null
    username    = null
  }
  description = "Git credentials for Config Sync"
  sensitive   = true
  type = object({
    secret_name = string
    token       = string
    username    = string
  })
  # TODO: Add validations
}

variable "configmanagement_policy_dir" {
  default     = ""
  description = "The path within the sync repository that represents the top level to sync"
  type        = string
}

variable "configmanagement_prevent_drift" {
  default     = true
  description = "Enable the Config Sync admission webhook to prevent drift"
  type        = bool
}

variable "configmanagement_sync_branch" {
  default     = "main"
  description = "Branch in the sync repository to use for Config Sync"
  type        = string
}

variable "configmanagement_sync_repo" {
  default     = null
  description = "Repository to use for Config Sync"
  type        = string
}
