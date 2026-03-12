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
  ira_inference_perf_bench_manifests_directory                 = "${path.module}/../../kubernetes-manifests/inference-perf-bench"
  ira_batch_cpu_load_generator_image_url                       = var.ira_batch_cpu_load_generator_image_url != null ? var.ira_batch_cpu_load_generator_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/batch-load-generator:latest"
  ira_batch_cpu_load_generator_kubernetes_namespace_name       = var.ira_batch_cpu_load_generator_kubernetes_namespace_name != null ? var.ira_batch_cpu_load_generator_kubernetes_namespace_name : "${local.unique_identifier_prefix}-batch-load-generator-cpu"
  ira_batch_cpu_load_generator_kubernetes_service_account_name = var.ira_batch_cpu_load_generator_kubernetes_service_account_name != null ? var.ira_batch_cpu_load_generator_kubernetes_service_account_name : "${local.unique_identifier_prefix}-batch-load-generator-cpu"

  ira_batch_cpu_pubsub_subscriber_image_url                       = var.ira_batch_cpu_pubsub_subscriber_image_url != null ? var.ira_batch_cpu_pubsub_subscriber_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/batch-pubsub-subscriber:latest"
  ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name       = var.ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name != null ? var.ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name : "${local.unique_identifier_prefix}-batch-pubsub-subscriber-cpu"
  ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name = var.ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name != null ? var.ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name : "${local.unique_identifier_prefix}-batch-pubsub-subscriber-cpu"

  ira_batch_gpu_kubernetes_namespace_name       = var.ira_batch_gpu_kubernetes_namespace_name != null ? var.ira_batch_gpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-batch-gpu"
  ira_batch_gpu_kubernetes_service_account_name = var.ira_batch_gpu_kubernetes_service_account_name != null ? var.ira_batch_gpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-batch-gpu"
  ira_batch_gpu_vllm_image_url                  = var.ira_batch_gpu_vllm_image_url != null ? var.ira_batch_gpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/batch-gpu:latest"

  ira_batch_pubsub_prompt_messages_subscription_dead_letter_name = var.ira_batch_pubsub_prompt_messages_subscription_dead_letter_name != null ? var.ira_batch_pubsub_prompt_messages_subscription_dead_letter_name : "${local.unique_identifier_prefix}-prompt-messages-subscription-dead-letter"
  ira_batch_pubsub_prompt_messages_subscription_name             = var.ira_batch_pubsub_prompt_messages_subscription_name != null ? var.ira_batch_pubsub_prompt_messages_subscription_name : "${local.unique_identifier_prefix}-prompt-messages-subscription"
  ira_batch_pubsub_prompt_messages_topic_dead_letter_name        = var.ira_batch_pubsub_prompt_messages_topic_dead_letter_name != null ? var.ira_batch_pubsub_prompt_messages_topic_dead_letter_name : "${local.unique_identifier_prefix}-prompt-messages-topic-dead-letter"
  ira_batch_pubsub_prompt_messages_topic_name                    = var.ira_batch_pubsub_prompt_messages_topic_name != null ? var.ira_batch_pubsub_prompt_messages_topic_name : "${local.unique_identifier_prefix}-prompt-messages-topic"

  ira_offline_batch_cpu_dataset_downloader_image_url                       = var.ira_offline_batch_cpu_dataset_downloader_image_url != null ? var.ira_offline_batch_cpu_dataset_downloader_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/offline-batch-dataset-downloader:latest"
  ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name       = var.ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name != null ? var.ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name : "${local.unique_identifier_prefix}-offline-batch-dataset-downloader-cpu"
  ira_offline_batch_cpu_dataset_downloader_kubernetes_service_account_name = var.ira_offline_batch_cpu_dataset_downloader_kubernetes_service_account_name != null ? var.ira_offline_batch_cpu_dataset_downloader_kubernetes_service_account_name : "${local.unique_identifier_prefix}-offline-batch-dataset-downloader-cpu"

  ira_offline_batch_cpu_worker_image_url                       = var.ira_offline_batch_cpu_worker_image_url != null ? var.ira_offline_batch_cpu_worker_image_url : "${local.cloudbuild_ar_image_repository_url}/cpu/offline-batch-worker:latest"
  ira_offline_batch_cpu_worker_kubernetes_namespace_name       = var.ira_offline_batch_cpu_worker_kubernetes_namespace_name != null ? var.ira_offline_batch_cpu_worker_kubernetes_namespace_name : "${local.unique_identifier_prefix}-offline-batch-worker-cpu"
  ira_offline_batch_cpu_worker_kubernetes_service_account_name = var.ira_offline_batch_cpu_worker_kubernetes_service_account_name != null ? var.ira_offline_batch_cpu_worker_kubernetes_service_account_name : "${local.unique_identifier_prefix}-offline-batch-worker-cpu"

  ira_offline_batch_dataset_bucket_name = var.ira_offline_batch_dataset_bucket_name != null ? var.ira_offline_batch_dataset_bucket_name : "${local.ira_offline_batch_project_id}-${local.unique_identifier_prefix}-dataset"

  ira_offline_batch_gpu_kubernetes_namespace_name       = var.ira_offline_batch_gpu_kubernetes_namespace_name != null ? var.ira_offline_batch_gpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-offline-batch-gpu"
  ira_offline_batch_gpu_kubernetes_service_account_name = var.ira_offline_batch_gpu_kubernetes_service_account_name != null ? var.ira_offline_batch_gpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-offline-batch-gpu"
  ira_offline_batch_gpu_vllm_image_url                  = var.ira_offline_batch_gpu_vllm_image_url != null ? var.ira_offline_batch_gpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/offline-batch-gpu:latest"

  ira_offline_batch_project_id = var.ira_offline_batch_project_id != null ? var.ira_offline_batch_project_id : var.platform_default_project_id

  ira_online_gpu_diffusers_flux_image_url        = var.ira_online_gpu_diffusers_flux_image_url != null ? var.ira_online_gpu_diffusers_flux_image_url : "${local.cloudbuild_ar_image_repository_url}/gpu-diffusers/flux:latest"
  ira_online_gpu_kubernetes_namespace_name       = var.ira_online_gpu_kubernetes_namespace_name != null ? var.ira_online_gpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-online-gpu"
  ira_online_gpu_kubernetes_service_account_name = var.ira_online_gpu_kubernetes_service_account_name != null ? var.ira_online_gpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-online-gpu"
  ira_online_gpu_vllm_image_url                  = var.ira_online_gpu_vllm_image_url != null ? var.ira_online_gpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/gpu:latest"

  ira_online_tpu_kubernetes_namespace_name       = var.ira_online_tpu_kubernetes_namespace_name != null ? var.ira_online_tpu_kubernetes_namespace_name : "${local.unique_identifier_prefix}-online-tpu"
  ira_online_tpu_kubernetes_service_account_name = var.ira_online_tpu_kubernetes_service_account_name != null ? var.ira_online_tpu_kubernetes_service_account_name : "${local.unique_identifier_prefix}-online-tpu"
  ira_online_tpu_max_diffusion_sdxl_image_url    = var.ira_online_tpu_max_diffusion_sdxl_image_url != null ? var.ira_online_tpu_max_diffusion_sdxl_image_url : "${local.cloudbuild_ar_image_repository_url}/tpu-max-diffusion/sdxl:latest"
  ira_online_tpu_vllm_image_url                  = var.ira_online_tpu_vllm_image_url != null ? var.ira_online_tpu_vllm_image_url : "${local.cloudbuild_ar_image_repository_url}/vllm/tpu:latest"

  ira_inference_perf_ksa_project_roles_list                = ["roles/logging.viewer", "roles/monitoring.viewer", "roles/monitoring.metricsScopesViewer", "roles/storage.bucketViewer"]
  ira_inference_perf_bench_kubernetes_service_account_name = var.ira_inference_perf_bench_kubernetes_service_account_name != null ? var.ira_inference_perf_bench_kubernetes_service_account_name : "${local.unique_identifier_prefix}-inference-perf-bench"
  hub_models_bucket_bench_results_name                     = var.hub_models_bucket_bench_results_name != null ? var.hub_models_bucket_bench_results_name : "${local.unique_identifier_prefix}-bench-results"
  hub_models_bucket_bench_dataset_name                     = var.hub_models_bucket_bench_dataset_name != null ? var.hub_models_bucket_bench_dataset_name : "${local.unique_identifier_prefix}-bench-dataset"

}

variable "ira_batch_cpu_load_generator_image_url" {
  default     = null
  description = "The URL for the CPU batch load generator container image."
  type        = string
}

variable "ira_batch_cpu_load_generator_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the batch CPU load generator workloads."
  type        = string
}

variable "ira_batch_cpu_load_generator_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the batch CPU load generator workloads."
  type        = string
}

variable "ira_batch_cpu_pubsub_subscriber_image_url" {
  default     = null
  description = "The URL for the CPU batch pubsub subscriber container image."
  type        = string
}

variable "ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the batch CPU pubsub subscriber workloads."
  type        = string
}

variable "ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the batch CPU pubsub subscriber workloads."
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

variable "ira_batch_gpu_vllm_image_url" {
  default     = "docker.io/vllm/vllm-openai:v0.11.2"
  description = "The URL for the batch GPU vLLM container image."
  type        = string
}

variable "ira_batch_pubsub_prompt_messages_subscription_dead_letter_name" {
  default     = null
  description = "The name of the dead letter subscription for prompt messages."
  type        = string
}

variable "ira_batch_pubsub_prompt_messages_subscription_name" {
  default     = null
  description = "The name of the Pub/Sub subscription for prompt messages."
  type        = string
}

variable "ira_batch_pubsub_prompt_messages_topic_dead_letter_name" {
  default     = null
  description = "The name of the dead letter topic for prompt messages."
  type        = string
}

variable "ira_batch_pubsub_prompt_messages_topic_name" {
  default     = null
  description = "The name of the Pub/Sub topic for prompt messages."
  type        = string
}

variable "ira_offline_batch_cpu_dataset_downloader_image_url" {
  default     = null
  description = "The URL for the CPU offline batch dataset downloader container image."
  type        = string
}

variable "ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the offline batch CPU dataset downloader workloads."
  type        = string
}

variable "ira_offline_batch_cpu_dataset_downloader_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the offline batch CPU dataset downloader workloads."
  type        = string
}

variable "ira_offline_batch_cpu_worker_image_url" {
  default     = null
  description = "The URL for the CPU offline batch worker container image."
  type        = string
}

variable "ira_offline_batch_cpu_worker_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the offline batch CPU worker workloads."
  type        = string
}

variable "ira_offline_batch_cpu_worker_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the offline batch CPU worker workloads."
  type        = string
}

variable "ira_offline_batch_dataset_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store the offline batch dataset."
  type        = string
}

variable "ira_offline_batch_gpu_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the offline batch GPU inference workloads."
  type        = string
}

variable "ira_offline_batch_gpu_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the offline batch GPU inference workloads."
  type        = string
}

variable "ira_offline_batch_gpu_vllm_image_url" {
  default     = "docker.io/vllm/vllm-openai:v0.11.2"
  description = "The URL for the batch GPU vLLM container image."
  type        = string
}

variable "ira_offline_batch_project_id" {
  default     = null
  description = "The GCP project ID for the offline batch inference workloads."
  type        = string
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

variable "ira_inference_perf_bench_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the inference-perf benchmarking job."
  type        = string
}

variable "hub_models_bucket_bench_results_name" {
  default     = null
  description = "The GCS bucket name for storage of inference-perf results."
  type        = string
}

variable "hub_models_bucket_bench_dataset_name" {
  default     = null
  description = "The GCS bucket name for storage of inference-perf dataset."
  type        = string
}

variable "enable_gpu" {
  default     = false
  description = "Turns on inference-perf resources for GPU cluster"
  type        = bool
}

variable "enable_tpu" {
  default     = false
  description = "Turns on inference-perf resources for TPU cluster"
  type        = bool
}

