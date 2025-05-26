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

output "comfyui_app_name" {
  description = "App name for the COmfyUI deployment."
  value       = var.comfyui_app_name
}

output "comfyui_artifact_registry_repository_id" {
  description = "The ID of the Artifact Registry repository for ComfyUI container images."
  value       = google_artifact_registry_repository.comfyui_container_images.repository_id
}

output "comfyui_deployment_namespace" {
  description = "The namespace of the GKE cluster that runs ComfyUI deployment."
  value       = var.comfyui_kubernetes_namespace
}

output "comfyui_endpoints_service_id" {
  description = "The ID of the ComfyUI Endpoints service."
  value       = google_endpoints_service.comfyui_https.id
}

output "comfyui_endpoints_service_name" {
  description = "The fully qualified service name of the ComfyUI Endpoints service."
  value       = google_endpoints_service.comfyui_https.service_name
}

output "comfyui_oauth_secret_name" {
  description = "The name of the Kubernetes secret holding the ComfyUI OAuth client secret."
  value       = kubernetes_secret_v1.comfyui_oauth.metadata[0].name
}

output "comfyui_storage_bucket_names" {
  description = "List of Cloud Storage bucket names"
  value = [
    for bucket in google_storage_bucket.comfyui_storage_buckets : bucket.name
  ]
}

output "custom_cloudbuild_service_account_email" {
  description = "The email address of the custom Cloud Build service account."
  value       = google_service_account.custom_cloudbuild_sa.email
}

output "docker_staging_bucket_name" {
  description = "The name of the Docker staging bucket."
  value       = google_storage_bucket.docker_staging_bucket.name
}

output "external_gateway_https_ip_address" {
  description = "The global static IP address reserved for the external HTTPS gateway."
  value       = google_compute_global_address.external_gateway_https.address
}

output "external_gateway_https_name" {
  description = "The name of the global static IP address reserved for the external HTTPS gateway."
  value       = google_compute_global_address.external_gateway_https.name
}

output "external_gateway_ssl_certificate_domains" {
  description = "The list of domains managed by the external gateway SSL certificate."
  value       = google_compute_managed_ssl_certificate.external_gateway.managed.0.domains
}

output "external_gateway_ssl_certificate_name" {
  description = "The name of the Google Compute Managed SSL Certificate for the external gateway."
  value       = google_compute_managed_ssl_certificate.external_gateway.name
}

output "iap_client_id" {
  description = "The OAuth client ID for the ComfyUI IAP client."
  value       = google_iap_client.comfyui_client.client_id
}

output "environment_configuration" {
  value = <<EOT
GKE_CLUSTER_NAME="${local.cluster_name}"
GKE_CLUSTER_REGION="${var.cluster_region}"
GKE_PROJECT_ID="${var.cluster_project_id}"
COMFYUI_NAMESPACE="${var.comfyui_kubernetes_namespace}"
COMFYUI_APP_NAME="${var.comfyui_app_name}"
ACCELERATOR="${var.comfyui_accelerator_type}"
COMFYUI_URL="${google_endpoints_service.comfyui_https.id}"
CUSTOM_SA="${google_service_account.custom_cloudbuild_sa.id}"
COMFYUI_MODEL_BUCKET="${google_storage_bucket.comfyui_storage_buckets["comfyui-models"].name}"
COMFYUI_INPUT_BUCKET="${google_storage_bucket.comfyui_storage_buckets["comfyui-input"].name}"
COMFYUI_OUTPUT_BUCKET="${google_storage_bucket.comfyui_storage_buckets["comfyui-output"].name}"
STAGING_BUCKET="${google_storage_bucket.docker_staging_bucket.name}"
EOT
}
