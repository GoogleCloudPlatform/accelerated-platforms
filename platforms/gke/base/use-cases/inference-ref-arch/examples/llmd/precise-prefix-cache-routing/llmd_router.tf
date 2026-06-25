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

data "http" "llmd_ppcr_router_base_values" {
  url = local.llmd_ppcr_router_base_helm_values
}

data "http" "llmd_ppcr_router_guide_values" {
  url = local.llmd_ppcr_router_guide_helm_values
}

data "http" "llmd_ppcr_router_feature_values" {
  url = local.llmd_ppcr_router_feature_helm_values
}

data "helm_template" "llmd_ppcr_router" {
  name         = var.llmd_ppcr_guide_name
  namespace    = local.llmd_namespace
  kube_version = var.llmd_ppcr_kubernetes_version_router_templates

  repository = var.llmd_ppcr_router_chart_repo
  chart      = var.llmd_ppcr_router_chart
  version    = var.llmd_ppcr_router_chart_version

  values = [
    data.http.llmd_ppcr_router_base_values.response_body,
    data.http.llmd_ppcr_router_guide_values.response_body,
    data.http.llmd_ppcr_router_feature_values.response_body,
    yamlencode({
      provider = {
        name = var.llmd_ppcr_gateway_provider_name
      }
    })
  ]
  skip_tests = var.llmd_ppcr_skip_router_render_tests
  validate   = var.llmd_ppcr_validate_router_manifests
}

resource "local_file" "llmd_ppcr_router_manifests" {
  filename = "${local.namespace_directory}/${local.llmd_namespace}/router/llmd_ppcr_router.yaml"
  content  = data.helm_template.llmd_ppcr_router.manifest
}

module "kubectl_apply_llmd_ppcr_router_manifests" {
  source                      = "../../../../../modules/kubectl_apply"
  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.llmd_ppcr_router_manifests.filename
  manifest_includes_namespace = false
  namespace                   = local.llmd_namespace
}
