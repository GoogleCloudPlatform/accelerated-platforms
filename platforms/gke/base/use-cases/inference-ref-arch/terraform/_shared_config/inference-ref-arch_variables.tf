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
# - shared_config/platform_variables.tf
#

locals {
  ira_online_gpu_diffusers_flux_image_url        = var.ira_online_gpu_diffusers_flux_image_url != null ? var.ira_online_gpu_diffusers_flux_image_url : "${local.cloudbuild_ar_image_repository_url}/gpu-diffusers/flux:latest"
  ira_online_gpu_kubernetes_namespace_name       = var.ira_online_gpu_kubernetes_namespace_name != null ? var.ira_online_gpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-online-gpu"
  ira_online_gpu_kubernetes_service_account_name = var.ira_online_gpu_kubernetes_service_account_name != null ? var.ira_online_gpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-online-gpu"
  ira_online_gpu_vllm_image_url                  = var.ira_online_gpu_vllm_image_url != null ? var.ira_online_gpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/gpu:latest"

  ira_online_tpu_kubernetes_namespace_name       = var.ira_online_tpu_kubernetes_namespace_name != null ? var.ira_online_tpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-online-tpu"
  ira_online_tpu_kubernetes_service_account_name = var.ira_online_tpu_kubernetes_service_account_name != null ? var.ira_online_tpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-online-tpu"
  ira_online_tpu_max_diffusion_sdxl_image_url    = var.ira_online_tpu_max_diffusion_sdxl_image_url != null ? var.ira_online_tpu_max_diffusion_sdxl_image_url : "${local.cloudbuild_ar_image_repository_url}/tpu-max-diffusion/sdxl:latest"
  ira_online_tpu_vllm_image_url                  = var.ira_online_tpu_vllm_image_url != null ? var.ira_online_tpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/tpu:latest"

  ira_online_cpu_batch_load_generator_image_url    = var.ira_online_cpu_batch_load_generator_image_url != null ? var.ira_online_cpu_batch_load_generator_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/batch-load-generator:latest"
  ira_online_cpu_batch_pubsub_subscriber_image_url = var.ira_online_cpu_batch_pubsub_subscriber_image_url != null ? var.ira_online_cpu_batch_pubsub_subscriber_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/batch-pubsub-subscriber:latest"

  ira_batch_gpu_kubernetes_namespace_name                         = var.ira_batch_gpu_kubernetes_namespace_name != null ? var.ira_batch_gpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-batch-gpu"
  ira_batch_gpu_kubernetes_service_account_name                   = var.ira_batch_gpu_kubernetes_service_account_name != null ? var.ira_batch_gpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-batch-gpu"
  ira_batch_gpu_pubsub_subscriber_kubernetes_service_account_name = var.ira_batch_gpu_pubsub_subscriber_kubernetes_service_account_name != null ? var.ira_batch_gpu_pubsub_subscriber_kubernetes_service_account_name : "${local.ira_batch_gpu_kubernetes_service_account_name}-pubsub-subscriber"
  ira_batch_gpu_vllm_image_url                                    = var.ira_batch_gpu_vllm_image_url != null ? var.ira_batch_gpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/batch-gpu:latest"
}

variable "ira_online_gpu_diffusers_flux_image_url" {
  default     = null
  description = "The URL for the GPU Diffusers Flux container image."
  type        = string
}

variable "ira_online_gpu_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the online GPU inference workloads."
  type        = string
}

variable "ira_online_gpu_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the online GPU inference workloads."
  type        = string
}

variable "ira_online_gpu_vllm_image_url" {
  default     = "docker.io/vllm/vllm-openai:v0.11.2"
  description = "The URL for the GPU vLLM container image."
  type        = string
}

variable "ira_online_tpu_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the online TPU inference workloads."
  type        = string
}

variable "ira_online_tpu_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the online TPU inference workloads."
  type        = string
}

variable "ira_online_tpu_max_diffusion_sdxl_image_url" {
  default     = null
  description = "The URL for the TPU MaxDiffusion SDXL container image."
  type        = string
}

variable "ira_online_tpu_vllm_image_url" {
  default     = "docker.io/vllm/vllm-tpu:v0.11.1"
  description = "The URL for the TPU vLLM container image."
  type        = string
}

variable "ira_batch_gpu_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the batch GPU inference workloads."
  type        = string
}

variable "ira_batch_gpu_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the batch GPU inference workloads."
  type        = string
}

variable "ira_batch_gpu_pubsub_subscriber_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the pubsub subscriber workloads."
  type        = string
}

variable "ira_batch_gpu_vllm_image_url" {
  default     = "docker.io/vllm/vllm-openai:v0.11.2"
  description = "The URL for the batch GPU vLLM container image."
  type        = string
}

variable "ira_online_cpu_batch_load_generator_image_url" {
  default     = null
  description = "The URL for the CPU batch load generator container image."
  type        = string
}

variable "ira_online_cpu_batch_pubsub_subscriber_image_url" {
  default     = null
  description = "The URL for the CPU batch pubsub subscriber container image."
  type        = string
}
