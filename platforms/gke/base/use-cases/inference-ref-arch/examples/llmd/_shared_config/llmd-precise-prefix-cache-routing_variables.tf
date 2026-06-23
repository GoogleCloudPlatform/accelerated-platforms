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
  llmd_ppcr_gateway_remote_manifest    = "${var.llmd_ppcr_git_url}/${var.llmd_ppcr_git_org}/${var.llmd_ppcr_git_repo}//guides/recipes/gateway/${var.llmd_ppcr_gateway_type}?ref=${var.llmd_ppcr_git_branch}"
  llmd_ppcr_router_base_helm_values    = "${var.llmd_ppcr_git_raw_url_prefix}/${var.llmd_ppcr_git_org}/${var.llmd_ppcr_git_repo}/${var.llmd_ppcr_git_branch}/guides/recipes/router/base.values.yaml"
  llmd_ppcr_router_feature_helm_values = "${var.llmd_ppcr_git_raw_url_prefix}/${var.llmd_ppcr_git_org}/${var.llmd_ppcr_git_repo}/${var.llmd_ppcr_git_branch}/guides/recipes/router/features/httproute-flags.yaml"
  llmd_ppcr_router_guide_helm_values   = "${var.llmd_ppcr_git_raw_url_prefix}/${var.llmd_ppcr_git_org}/${var.llmd_ppcr_git_repo}/${var.llmd_ppcr_git_branch}/guides/${var.llmd_ppcr_guide_name}/router/${var.llmd_ppcr_guide_name}.values.yaml"
}

variable "llmd_ppcr_gateway_provider_name" {
  default     = "gke"
  description = "Gateway provider for llmd"
  type        = string
}

variable "llmd_ppcr_git_raw_url_prefix" {
  default     = "https://raw.githubusercontent.com"
  description = "Prefix to the git url for llmd repo"
  type        = string
}

variable "llmd_ppcr_git_url" {
  default     = "https://github.com"
  description = "Prefix to the git url for llmd repo"
  type        = string
}

variable "llmd_ppcr_git_branch" {
  default     = "main"
  description = "Branch of the llmd repository."
  type        = string
}

variable "llmd_ppcr_git_org" {
  default     = "llm-d"
  description = "GitHub Organization where llmd repo is created."
  type        = string
}

variable "llmd_ppcr_git_repo" {
  default     = "llm-d"
  description = "Name of GitHub repository."
  type        = string
}

variable "llmd_ppcr_gateway_type" {
  default     = "gke-l7-rilb"
  description = "Gateway type for llmd"
  type        = string
}
variable "llmd_ppcr_guide_name" {
  default     = "precise-prefix-cache-routing"
  description = "llmd guide name."
  type        = string
}

variable "llmd_ppcr_kubernetes_version_router_templates" {
  default     = "1.28.0"
  description = "The Kubernetes version to use when templating."
  type        = string
}

variable "llmd_ppcr_router_chart" {
  default     = "llm-d-router-gateway-dev"
  description = "Helm chart repo that holds llm charts"
  type        = string
}

variable "llmd_ppcr_router_chart_repo" {
  default     = "oci://ghcr.io/llm-d/charts"
  description = "Helm chart for installing router"
  type        = string
}

variable "llmd_ppcr_router_chart_version" {
  default     = "v0"
  description = "Helm chart version for installing router"
  type        = string
}

variable "llmd_ppcr_skip_router_render_tests" {
  default     = false
  description = "If set, tests will not be rendered. By default, tests are rendered."
  type        = bool
}

variable "llmd_ppcr_validate_router_manifests" {
  default     = false
  description = "Validate the manifests against the Kubernetes cluster."
  type        = bool
}
