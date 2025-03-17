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

# Configuration dependencies
# - shared_config/cluster_variables.tf
# - shared_config/platform_variables.tf

locals {
  fine_tuning_ar_repository_id  = "${local.unique_identifier_prefix}-fine-tuning"
  fine_tuning_ar_repository_url = "${var.cluster_region}-docker.pkg.dev/${local.fine_tuning_project_id}/${local.fine_tuning_ar_repository_id}"

  fine_tuning_bucket_cloudbuild_name = "${var.cluster_project_id}-${local.unique_identifier_prefix}-cloudbuild"
  fine_tuning_bucket_data_name       = "${var.cluster_project_id}-${local.unique_identifier_prefix}-data"
  fine_tuning_bucket_model_name      = "${var.cluster_project_id}-${local.unique_identifier_prefix}-model"

  fine_tuning_kubeconfig_directory = "${path.module}/../../../../../kubernetes/kubeconfig"
  fine_tuning_kubeconfig_file      = "${local.fine_tuning_kubeconfig_directory}/${local.kubeconfig_file_name}"

  fine_tuning_manifests_directory                = "${path.module}/../../../../../kubernetes/manifests"
  fine_tuning_namespace_manifests_directory      = "${local.fine_tuning_manifests_directory}/namespace"
  fine_tuning_team_namespace_manifests_directory = "${local.fine_tuning_namespace_manifests_directory}/${var.fine_tuning_team_namespace}"

  fine_tuning_project_id = var.fine_tuning_project_id != null ? var.fine_tuning_project_id : var.cluster_project_id
  fine_tuning_region     = var.fine_tuning_region != null ? var.fine_tuning_region : var.cluster_region
}

variable "fine_tuning_team_namespace" {
  default     = "ml-team"
  description = "The Kubernetes namespace to use for fine-tuning workloads."
  type        = string
}

variable "fine_tuning_project_id" {
  default     = null
  description = "The Google Cloud project where the fine-tuning resources will be created."
  type        = string
}

variable "fine_tuning_region" {
  default     = null
  description = "The Google Cloud region where the fine-tuning resources will be created."
  type        = string
}
