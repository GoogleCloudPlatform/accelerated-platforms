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
locals {
  ira_auto_tuning_vllm_kubernetes_namespace_name       = var.ira_auto_tuning_vllm_kubernetes_namespace_name != null ? var.ira_auto_tuning_vllm_kubernetes_namespace_name : "${local.unique_identifier_prefix}-auto-tuning-vllm"
  ira_auto_tuning_vllm_kubernetes_service_account_name = var.ira_auto_tuning_vllm_kubernetes_service_account_name != null ? var.ira_auto_tuning_vllm_kubernetes_service_account_name : "${local.unique_identifier_prefix}-auto-tuning-vllm-ksa"
  ira_auto_tuning_vllm_results_bucket                  = var.ira_auto_tuning_vllm_results_bucket != null ? var.ira_auto_tuning_vllm_results_bucket : "${local.unique_identifier_prefix}-auto-tuning-vllm-results"
  ira_auto_tuning_vllm_secretproviderclass             = var.ira_auto_tuning_vllm_secretproviderclass != null ? var.ira_auto_tuning_vllm_secretproviderclass : "huggingface-token-read"
}

variable "ira_auto_tuning_vllm_kubernetes_namespace_name" {
  default     = null
  description = "The Kubernetes namespace for the batch CPU load generator workloads."
  type        = string
}

variable "ira_auto_tuning_vllm_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes service account for the batch CPU load generator workloads."
  type        = string
}

variable "ira_auto_tuning_vllm_results_bucket" {
  default     = null
  description = "The GCS bucket for storing auto-tuning results."
  type        = string
}

variable "ira_auto_tuning_vllm_secretproviderclass" {
  default     = null
  description = "The Secretproviderclass to access huggingface read token."
  type        = string
}
