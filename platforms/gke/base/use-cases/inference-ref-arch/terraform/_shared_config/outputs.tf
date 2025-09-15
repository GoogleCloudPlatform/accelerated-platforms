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

output "comfyui_accelerator_type" {
  value = var.comfyui_accelerator_type
}

output "comfyui_app_name" {
  value = var.comfyui_app_name
}

output "comfyui_cloud_storage_model_bucket_name" {
  value = local.comfyui_cloud_storage_model_bucket_name
}

output "comfyui_cloudbuild_source_bucket_name" {
  value = local.comfyui_cloudbuild_source_bucket_name
}

output "comfyui_cloudbuild_service_account_id" {
  value = local.comfyui_cloudbuild_service_account_id
}

output "comfyui_endpoints_hostname" {
  value = local.comfyui_endpoints_hostname
}

output "comfyui_iap_oath_branding_project_id" {
  value = local.comfyui_iap_oath_branding_project_id
}

output "comfyui_kubernetes_namespace" {
  value = var.comfyui_kubernetes_namespace
}

output "comfyui_ssl_certificate_name" {
  value = local.comfyui_endpoints_ssl_certificate_name
}

output "ira_online_gpu_diffusers_flux_image_url" {
  value = local.ira_online_gpu_diffusers_flux_image_url
}

output "ira_online_gpu_kubernetes_namespace_name" {
  value = local.ira_online_gpu_kubernetes_namespace_name
}

output "ira_online_gpu_kubernetes_service_account_name" {
  value = local.ira_online_gpu_kubernetes_service_account_name
}

output "ira_online_tpu_kubernetes_namespace_name" {
  value = local.ira_online_tpu_kubernetes_namespace_name
}

output "ira_online_tpu_kubernetes_service_account_name" {
  value = local.ira_online_tpu_kubernetes_service_account_name
}

output "use_case" {
  value = "inference-ref-arch"
}

output "workflow_api_endpoints_hostname" {
  value = local.workflow_api_endpoints_hostname
}

output "workflow_api_endpoints_ssl_certificate_name" {
  value = local.workflow_api_endpoints_ssl_certificate_name
}

output "workflow_api_service_account_email" {
  value = local.workflow_api_service_account_email
}

output "workflow_api_service_account_oauth_display_name" {
  value = local.workflow_api_service_account_oauth_display_name
}

output "workflow_api_service_account_project_id" {
  value = local.workflow_api_service_account_project_id
}
