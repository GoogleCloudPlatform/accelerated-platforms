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

locals {
  sft_tpu_maxtext_single_host_project_id                      = var.sft_tpu_maxtext_single_host_project_id != null ? var.sft_tpu_maxtext_single_host_project_id : var.platform_default_project_id
  sft_tpu_maxtext_single_host_image_url                       = var.sft_tpu_maxtext_single_host_image_url != null ? var.sft_tpu_maxtext_single_host_image_url : "${local.cloudbuild_ar_image_repository_url}/training-ref-arch/sft-tpu-maxtext-single-host:latest"
  sft_tpu_maxtext_single_host_kubernetes_namespace_name       = var.sft_tpu_maxtext_single_host_kubernetes_namespace_name != null ? var.sft_tpu_maxtext_single_host_kubernetes_namespace_name : "${local.unique_identifier_prefix}-sft-tpu-maxtext-sh"
  sft_tpu_maxtext_single_host_kubernetes_service_account_name = var.sft_tpu_maxtext_single_host_kubernetes_service_account_name != null ? var.sft_tpu_maxtext_single_host_kubernetes_service_account_name : "${local.unique_identifier_prefix}-sft-tpu-maxtext-sa"
  sft_tpu_maxtext_single_host_dataset_bucket_name             = var.sft_tpu_maxtext_single_host_dataset_bucket_name != null ? var.sft_tpu_maxtext_single_host_dataset_bucket_name : "${local.sft_tpu_maxtext_single_host_project_id}-${local.unique_identifier_prefix}-sft-tpu-maxtext-sh-dataset"
}

variable "sft_tpu_maxtext_single_host_project_id" {
  default     = null
  description = "The Google Cloud project where the SFT resources will be created."
  type        = string
}

variable "sft_tpu_maxtext_single_host_image_url" {
  default     = null
  description = "The URL for the SFT on TPU container image."
  type        = string
}

variable "sft_tpu_maxtext_single_host_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace name for the SFT on TPU deployment."
  type        = string
}

variable "sft_tpu_maxtext_single_host_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account name for the SFT on TPU deployment."
  type        = string
}

variable "sft_tpu_maxtext_single_host_dataset_bucket_name" {
  default     = null
  description = "The GCP bucket name for the SFT dataset."
  type        = string
}
