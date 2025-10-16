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

output "cloudbuild_cws_image_pipeline_git_namespace" {
  value = var.cloudbuild_cws_image_pipeline_git_namespace
}

output "cloudbuild_cws_image_registry_name" {
  value = local.cloudbuild_cws_image_registry_name
}

output "cloudbuild_cws_image_registry_upstream_name" {
  value = local.cloudbuild_cws_image_registry_upstream_name
}

output "platform_default_project_id" {
  value = var.platform_default_project_id
}

output "platform_name" {
  value = var.platform_name
}

output "platform_resource_name_prefix" {
  value = var.platform_resource_name_prefix
}

output "terraform_bucket_name" {
  value = local.terraform_bucket_name
}

output "terraform_project_id" {
  value = local.terraform_project_id
}

output "workstation_cluster_name" {
  value = local.workstation_cluster_name
}

output "workstation_cluster_project_id" {
  value = local.workstation_cluster_project_id
}

output "workstation_cluster_region" {
  value = local.workstation_cluster_region
}
