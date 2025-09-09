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
# - shared_config/cloudbuild_variables.tf
# - shared_config/cluster_variables.tf
# - shared_config/platform_variables.tf
#

locals {
  comfyui_cloudbuild_project_id             = var.comfyui_cloudbuild_project_id != null ? var.comfyui_cloudbuild_project_id : local.cloudbuild_project_id
  comfyui_cloudbuild_service_account_email  = "${local.comfyui_cloudbuild_service_account_name}@${local.comfyui_cloudbuild_project_id}.iam.gserviceaccount.com"
  comfyui_cloudbuild_service_account_id     = "projects/${local.comfyui_cloudbuild_project_id}/serviceAccounts/${local.comfyui_cloudbuild_service_account_email}"
  comfyui_cloudbuild_service_account_name   = var.comfyui_cloudbuild_service_account_name != null ? var.comfyui_cloudbuild_service_account_name : local.cloudbuild_service_account_name
  comfyui_cloudbuild_source_bucket_location = var.comfyui_cloudbuild_source_bucket_location != null ? var.comfyui_cloudbuild_source_bucket_location : local.cloudbuild_location
  comfyui_cloudbuild_source_bucket_name     = var.comfyui_cloudbuild_source_bucket_name != null ? var.comfyui_cloudbuild_source_bucket_name : local.cloudbuild_source_bucket_name

  comfyui_cloud_storage_input_bucket_name    = var.comfyui_cloud_storage_input_bucket_name != null ? var.comfyui_cloud_storage_input_bucket_name : "${local.comfyui_cloud_storage_project_id}-${local.unique_identifier_prefix}-${local.comfyui_default_name}-input"
  comfyui_cloud_storage_location             = var.comfyui_cloud_storage_location != null ? var.comfyui_cloud_storage_location : local.cluster_region
  comfyui_cloud_storage_model_bucket_name    = var.comfyui_cloud_storage_model_bucket_name != null ? var.comfyui_cloud_storage_model_bucket_name : "${local.comfyui_cloud_storage_project_id}-${local.unique_identifier_prefix}-${local.comfyui_default_name}-models"
  comfyui_cloud_storage_output_bucket_name   = var.comfyui_cloud_storage_output_bucket_name != null ? var.comfyui_cloud_storage_output_bucket_name : "${local.comfyui_cloud_storage_project_id}-${local.unique_identifier_prefix}-${local.comfyui_default_name}-output"
  comfyui_cloud_storage_project_id           = var.comfyui_cloud_storage_project_id != null ? var.comfyui_cloud_storage_project_id : var.platform_default_project_id
  comfyui_cloud_storage_workflow_bucket_name = var.comfyui_cloud_storage_workflow_bucket_name != null ? var.comfyui_cloud_storage_workflow_bucket_name : "${local.comfyui_cloud_storage_project_id}-${local.unique_identifier_prefix}-${local.comfyui_default_name}-workflows"

  comfyui_default_name = "comfyui"

  comfyui_endpoints_hostname             = var.comfyui_endpoints_hostname != null ? var.comfyui_endpoints_hostname : "comfyui.${var.comfyui_kubernetes_namespace}.${local.unique_identifier_prefix}.endpoints.${local.cluster_project_id}.cloud.goog"
  comfyui_endpoints_ssl_certificate_name = "${local.unique_identifier_prefix}-${var.comfyui_kubernetes_namespace}-external-gateway"

  comfyui_gateway_address_name = "${local.unique_identifier_prefix}-${local.comfyui_default_name}-external-gateway-https"
  comfyui_gateway_name         = "external-https"

  comfyui_iap_oath_branding_project_id = var.comfyui_iap_oath_branding_project_id != null ? var.comfyui_iap_oath_branding_project_id : var.platform_default_project_id
}

variable "comfyui_accelerator_type" {
  default = "nvidia-l4"
  type    = string
}

variable "comfyui_app_name" {
  default = "comfyui"
  type    = string
}

variable "comfyui_artifact_repo_name" {
  default = "comfyui"
  type    = string
}

variable "comfyui_cloudbuild_project_id" {
  default = null
  type    = string
}

variable "comfyui_cloudbuild_service_account_name" {
  default = null
  type    = string
}

variable "comfyui_cloudbuild_source_bucket_location" {
  default = null
  type    = string
}

variable "comfyui_cloudbuild_source_bucket_name" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_input_bucket_name" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_location" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_model_bucket_name" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_output_bucket_name" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_project_id" {
  default = null
  type    = string
}

variable "comfyui_cloud_storage_workflow_bucket_name" {
  default = null
  type    = string
}

variable "comfyui_endpoints_hostname" {
  default = null
  type    = string
}

variable "comfyui_iap_domain" {
  default = null
  type    = string
}

variable "comfyui_iap_oath_branding_project_id" {
  default = null
  type    = string
}

variable "comfyui_image_name" {
  default = "comfyui"
  type    = string
}

variable "comfyui_image_staging_bucket" {
  default = "comfyui-image-staging"
  type    = string
}

variable "comfyui_image_tag" {
  default = "0.0.1"
  type    = string
}

variable "comfyui_kubernetes_namespace" {
  default = "comfyui"
  type    = string
}
