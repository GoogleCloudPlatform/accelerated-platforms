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

output "rl_cpu_reinforcement_learning_dataset_downloader_image_url" {
  value = local.rl_cpu_reinforcement_learning_dataset_downloader_image_url
}

output "rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_namespace_name" {
  value = local.rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_namespace_name
}

output "rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_service_account_name" {
  value = local.rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_service_account_name
}

output "rl_cpu_reinforcement_learning_model_converter_image_url" {
  value = local.rl_cpu_reinforcement_learning_model_converter_image_url
}

output "rl_cpu_reinforcement_learning_model_converter_kubernetes_namespace_name" {
  value = local.rl_cpu_reinforcement_learning_model_converter_kubernetes_namespace_name
}

output "rl_cpu_reinforcement_learning_model_converter_kubernetes_service_account_name" {
  value = local.rl_cpu_reinforcement_learning_model_converter_kubernetes_service_account_name
}

output "rl_dataset_bucket_name" {
  value = local.rl_dataset_bucket_name
}

output "rl_tpu_reinforcement_learning_on_tpu_image_url" {
  value = local.rl_tpu_reinforcement_learning_on_tpu_image_url
}
