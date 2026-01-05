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
  llm-d_default_name                   = "llm-d"
  llm-d_endpoints_ssl_certificate_name = "${local.unique_identifier_prefix}-${var.llm-d_kubernetes_namespace}-external-gateway"
  llm-d_endpoints_hostname             = var.llm-d_endpoints_hostname != null ? var.llm-d_endpoints_hostname : "llmd.${var.llm-d_kubernetes_namespace}.${local.unique_identifier_prefix}.endpoints.${local.cluster_project_id}.cloud.goog"
  llm-d_gateway_address_name           = "${local.unique_identifier_prefix}-${local.llm-d_default_name}-external-gateway-https"
  llm-d_backend_policy_name            = var.llm-d_backend_policy_name != null ? var.llm-d_backend_policy_name : "gaie-inference-scheduling"
  llm-d_inferencepool_name             = var.llm-d_inferencepool_name != null ? var.llm-d_inferencepool_name : "gaie-inference-scheduling"
}

variable "llm-d_endpoints_hostname" {
  default = null
  type    = string
}

variable "llm-d_kubernetes_namespace" {
  description = "The Kubernetes namespace to deploy the manifests to."
  type        = string
}

variable "llm-d_backend_policy_name" {
  description = "The name of the backend policy."
  default     = null
  type        = string
}

variable "kubernetes_namespace_create" {
  description = "Create the Kubernetes namespace."
  type        = bool
}

variable "kubernetes_version" {
  description = "The Kubernetes version to use when templating."
  type        = string
}

variable "validate_manifests" {
  description = "Validate the manifests against the Kubernetes cluster."
  type        = bool
}

variable "llm-d_release_name" {
  description = "Unique release name for the helm chart deployment."
  type        = any
}

variable "llm-d_infra_repo" {
  description = "Helm repo for llm-d infra"
  type        = string
}

variable "llm-d_infra_chart" {
  description = "Helm chart for llm-d infra"
  type        = string
}

variable "llm-d_infra_chart_version" {
  description = "Version of the Helm chart for llm-d infra"
  type        = string
}

variable "skip_tests" {
  description = "If set, tests will not be rendered. By default, tests are rendered."
  type        = bool
}

variable "gaie_chart" {
  description = "Helm chart for llm-d infra"
  type        = string
}

variable "gaie_chart_version" {
  description = "Version of the Helm chart for llm-d infra"
  type        = string
}

variable "llm-d_httproute_name_internal" {
  description = "Name of the internal http route."
  type        = string
}

variable "llm-d_httproute_name_external" {
  description = "Name of the external http route for gradio access."
  type        = string
}

variable "llm-d_gateway_name_internal" {
  description = "Name of the internal gateway."
  type        = string
}

variable "llm-d_gateway_name_external" {
  description = "Name of the external gateway for gradio access."
  type        = string
}

variable "llm-d_inferencepool_name" {
  description = "Name of the InferencePool that the LB will point to."
  type        = string
}

variable "llm-d_ms_repo" {
  description = "Helm repo for llm-d model server."
  type        = string
}

variable "llm-d_ms_chart" {
  description = "Helm chart for llm-d model server."
  type        = string
}

variable "llm-d_ms_chart_version" {
  description = "Version of the Helm chart for llm-d model server."
  type        = string
}

variable "llm-d_huggingface_spc" {
  description = "Name of the service provider class to store the huggingface secret"
  type        = string
}

variable "llm-d_modelserver_sa" {
  description = "Service Account name for running model server"
  type        = string
}

variable "llm-d_ms_deployment_name" {
  description = "Model server deployment name"
  type        = string
}

variable "llm-d_ms_proxy_image" {
  description = "image of the routing proxy in model server"
  type        = string
}

variable "llm-d_ms_cuda_image" {
  description = "CUDA image for model server deployment"
  type        = string
}

variable "llm-d_model_name" {
  description = "model to server"
  type        = string

}
