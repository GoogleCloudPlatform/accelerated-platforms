# Copyright 2026 Google LLC
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
  rl_tpu_maxtext_grpo_single_host_image_url                       = var.rl_tpu_maxtext_grpo_single_host_image_url != null ? var.rl_tpu_maxtext_grpo_single_host_image_url : "${local.cloudbuild_ar_image_repository_url}/reinforcement-learning/rl-tpu-maxtext-grpo-single-host:latest"
  rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name       = var.rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name != null ? var.rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name : "${local.unique_identifier_prefix}-rl-tpu-maxtext-grpo-single-host"
  rl_tpu_maxtext_grpo_single_host_kubernetes_service_account_name = var.rl_tpu_maxtext_grpo_single_host_kubernetes_service_account_name != null ? var.rl_tpu_maxtext_grpo_single_host_kubernetes_service_account_name : "${local.unique_identifier_prefix}-rl-tpu-maxtext-grpo-single-host-sa"
}

variable "rl_tpu_maxtext_grpo_single_host_image_url" {
  default     = null
  description = "The URL for the RL on TPU container image."
  type        = string
}

variable "rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace name for the RL on TPU deployment."
  type        = string
}

variable "rl_tpu_maxtext_grpo_single_host_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account name for the RL on TPU deployment."
  type        = string
}
