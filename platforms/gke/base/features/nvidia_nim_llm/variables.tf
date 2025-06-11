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

variable "cluster_project_id" {
  description = "The project ID of the cluster."
  type        = string
}

variable "kubeconfig_file_name" {
  description = "The file name of the kubeconfig file."
  type        = string
}

variable "kubernetes_namespace" {
  default     = null
  description = "The Kubernetes namespace to deploy the manifests to."
  type        = string
}

variable "kubernetes_namespace_create" {
  default     = true
  description = "Create the Kubernetes namespace."
  type        = bool
}

variable "kubernetes_version" {
  default     = "1.23"
  description = "The Kubernetes version to use when templating."
  type        = string
}

variable "validate_manifests" {
  default     = false
  description = "Validate the manifests against the Kubernetes cluster."
  type        = bool
}

variable "nvidia_model_store_bucket_iam_roles" {
  default     = []
  description = "IAM roles to grant to the Kubernetes service account for the model store bucket."
  type        = list(string)
}

variable "nvidia_model_store_bucket_name" {
  description = "The name of the bucket for the NVIDIA model store."
  type        = string
}

variable "nvidia_model_store_bucket_project_id" {
  description = "The project ID of the bucket for the NVIDIA model store."
  type        = string
}

variable "nvidia_ncg_api_key_secret_manager_project_id" {
  description = "The project ID of the Secret Manager project containing the NCG API key secret"
  type        = string
}

variable "nvidia_ncg_api_key_secret_manager_secret_name" {
  description = "The name of the Secret Manager secret containing the NCG API key"
  type        = string
}

variable "nvidia_nim_llm_helm_chart_values" {
  description = "A list of strings containing the Helm chart values."
  type        = any
}

variable "nvidia_nim_llm_helm_chart_version" {
  default     = "1.7.0"
  description = "The version of the NVIDIA NIM LLM helm chart (https://catalog.ngc.nvidia.com/orgs/nim/helm-charts/nim-llm) to use."
  type        = string
}

variable "nvidia_nim_llm_helm_skip_tests" {
  default     = true
  description = "Whether to skip the rendering of the tests"
  type        = bool
}

variable "nvidia_nim_llm_release_name" {
  description = "Unique release name for the NVIDIA NIM LLM helm chart deployment."
  type        = any
}
