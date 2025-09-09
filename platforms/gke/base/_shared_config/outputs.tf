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

output "cloudbuild_github_access_token_read_secret_manager_secret_name" {
  value = local.cloudbuild_github_access_token_read_secret_manager_secret_name
}

output "cloudbuild_github_access_token_write_secret_manager_secret_name" {
  value = local.cloudbuild_github_access_token_write_secret_manager_secret_name
}

output "cloudbuild_location" {
  value = local.cloudbuild_location
}

output "cloudbuild_project_id" {
  value = local.cloudbuild_project_id
}

output "cloudbuild_service_account_email" {
  value = local.cloudbuild_service_account_email
}

output "cloudbuild_service_account_id" {
  value = local.cloudbuild_service_account_id
}

output "cloudbuild_source_bucket_name" {
  value = local.cloudbuild_source_bucket_name
}

output "cluster_autopilot_enabled" {
  value = var.cluster_autopilot_enabled
}

output "cluster_credentials_command" {
  value = local.cluster_credentials_command
}

output "cluster_gcsfuse_user_role" {
  value = local.cluster_gcsfuse_user_role
}

output "cluster_gcsfuse_viewer_role" {
  value = local.cluster_gcsfuse_viewer_role
}

output "cluster_name" {
  value = local.cluster_name
}

output "cluster_node_pool_service_account_project_id" {
  value = local.cluster_node_pool_service_account_project_id
}

output "cluster_project_id" {
  value = local.cluster_project_id
}

output "cluster_region" {
  value = local.cluster_region
}

output "huggingface_hub_access_token_read_secret_manager_secret_name" {
  value = local.huggingface_hub_access_token_read_secret_manager_secret_name
}

output "huggingface_hub_access_token_write_secret_manager_secret_name" {
  value = local.huggingface_hub_access_token_write_secret_manager_secret_name
}

output "huggingface_hub_downloader_kubernetes_namespace_name" {
  value = local.huggingface_hub_downloader_kubernetes_namespace_name
}

output "huggingface_hub_downloader_kubernetes_service_account_name" {
  value = local.huggingface_hub_downloader_kubernetes_service_account_name
}

output "huggingface_hub_downloader_service_account_id" {
  value = local.huggingface_hub_downloader_service_account_email
}

output "huggingface_hub_models_bucket_name" {
  value = local.huggingface_hub_models_bucket_name
}

output "huggingface_hub_models_bucket_project_id" {
  value = local.huggingface_hub_models_bucket_project_id
}

output "huggingface_secret_manager_project_id" {
  value = local.huggingface_secret_manager_project_id
}

output "nvidia_ncg_api_key_secret_manager_project_id" {
  value = local.nvidia_ncg_api_key_secret_manager_project_id
}

output "nvidia_ncg_api_key_secret_manager_secret_name" {
  value = local.nvidia_ncg_api_key_secret_manager_secret_name
}

output "nvidia_nim_model_store_bucket_name" {
  value = local.nvidia_nim_model_store_bucket_name
}

output "nvidia_nim_model_store_bucket_project_id" {
  value = local.nvidia_nim_model_store_bucket_project_id
}

output "platform_default_project_id" {
  value = var.platform_default_project_id
}

output "platform_name" {
  value = var.platform_name
}

output "terraform_bucket_name" {
  value = local.terraform_bucket_name
}

output "terraform_project_id" {
  value = local.terraform_project_id
}

output "resource_name_prefix" {
  value = var.resource_name_prefix
}

output "unique_identifier_prefix" {
  value = local.unique_identifier_prefix
}
