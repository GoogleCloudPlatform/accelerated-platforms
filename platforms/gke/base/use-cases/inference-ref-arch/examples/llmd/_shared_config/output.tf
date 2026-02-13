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

output "hub_models_bucket_bench_results_name" {
  value = local.hub_models_bucket_bench_results_name
}

output "hub_models_bucket_bench_dataset_name" {
  value = local.hub_models_bucket_bench_dataset_name
}

output "ira_batch_cpu_load_generator_image_url" {
  value = local.ira_batch_cpu_load_generator_image_url
}

output "ira_batch_cpu_load_generator_kubernetes_namespace_name" {
  value = local.ira_batch_cpu_load_generator_kubernetes_namespace_name
}

output "ira_batch_cpu_load_generator_kubernetes_service_account_name" {
  value = local.ira_batch_cpu_load_generator_kubernetes_service_account_name
}

output "ira_batch_cpu_pubsub_subscriber_image_url" {
  value = local.ira_batch_cpu_pubsub_subscriber_image_url
}

output "ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name" {
  value = local.ira_batch_cpu_pubsub_subscriber_kubernetes_namespace_name
}

output "ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name" {
  value = local.ira_batch_cpu_pubsub_subscriber_kubernetes_service_account_name
}

output "ira_batch_gpu_kubernetes_namespace_name" {
  value = local.ira_batch_gpu_kubernetes_namespace_name
}

output "ira_batch_gpu_kubernetes_service_account_name" {
  value = local.ira_batch_gpu_kubernetes_service_account_name
}

output "ira_batch_gpu_vllm_image_url" {
  value = local.ira_batch_gpu_vllm_image_url
}

output "ira_batch_pubsub_prompt_messages_subscription_name" {
  value = local.ira_batch_pubsub_prompt_messages_subscription_name
}

output "ira_batch_pubsub_prompt_messages_topic_dead_letter_name" {
  value = local.ira_batch_pubsub_prompt_messages_topic_dead_letter_name
}

output "ira_batch_pubsub_prompt_messages_topic_name" {
  value = local.ira_batch_pubsub_prompt_messages_topic_name
}

output "ira_inference_perf_bench_kubernetes_service_account_name" {
  value = local.ira_inference_perf_bench_kubernetes_service_account_name
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

output "ira_online_gpu_vllm_image_url" {
  value = local.ira_online_gpu_vllm_image_url
}

output "ira_online_tpu_kubernetes_namespace_name" {
  value = local.ira_online_tpu_kubernetes_namespace_name
}

output "ira_online_tpu_kubernetes_service_account_name" {
  value = local.ira_online_tpu_kubernetes_service_account_name
}

output "ira_online_tpu_max_diffusion_sdxl_image_url" {
  value = local.ira_online_tpu_max_diffusion_sdxl_image_url
}

output "ira_online_tpu_vllm_image_url" {
  value = local.ira_online_tpu_vllm_image_url
}

output "llmd_accelerator_type" {
  value = var.llmd_accelerator_type
}

output "llmd_endpoints_hostname" {
  value = local.llmd_endpoints_hostname
}

output "llmd_iap_oath_branding_project_id" {
  value = local.llmd_iap_oath_branding_project_id
}

output "llmd_ms_deployment_name" {
  value = local.llmd_ms_deployment_name
}

output "llmd_ssl_certificate_name" {
  value = local.llmd_endpoints_ssl_certificate_name
}

output "stress_test_service_account_email" {
  value = local.stress_test_service_account_email
}

output "stress_test_service_account_project_id" {
  value = local.stress_test_service_account_project_id
}

output "use_case" {
  value = "inference-ref-arch"
}
