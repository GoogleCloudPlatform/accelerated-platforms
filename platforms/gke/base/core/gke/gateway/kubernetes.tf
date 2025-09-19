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
  acp_root                        = "${path.module}/../../../../../.."
  kubernetes_kubeconfig_directory = "${local.acp_root}/platforms/gke/base/kubernetes/kubeconfig"
  kubernetes_manifests_directory  = "${local.acp_root}/platforms/gke/base/kubernetes/manifests"
  kubernetes_namespace_directory  = "${local.kubernetes_manifests_directory}/namespace"

  kubeconfig_file = "${local.kubernetes_kubeconfig_directory}/${local.kubeconfig_file_name}"

  my_kubernetes_namespace           = var.gke_gateway_kubernetes_namespace_name
  my_kubernetes_namespace_directory = "${local.kubernetes_namespace_directory}/${local.my_kubernetes_namespace}"
  my_kubernetes_namespace_file      = "${local.kubernetes_namespace_directory}/namespace-${local.my_kubernetes_namespace}.yaml"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

module "kubectl_apply_namespace" {
  depends_on = [
    local_file.namespace_yaml,
  ]

  source = "../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.namespace_yaml.filename
  manifest_includes_namespace = true
  source_content_hash         = local_file.namespace_yaml.content_sha512
}

module "kubectl_apply_gateway_manifests" {
  depends_on = [
    module.kubectl_apply_namespace,
  ]

  source = "../../../modules/kubectl_apply"

  apply_once                  = false
  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.my_kubernetes_namespace_directory}/gateways"
  manifest_includes_namespace = false
  namespace                   = local.my_kubernetes_namespace

  source_content_hash = sha512(
    join("",
      [
        "${local_file.gke_l7_global_external_managed_gateway_yaml.content_sha512}",
        "${local_file.gke_l7_regional_external_managed_gateway_yaml.content_sha512}",
        "${local_file.gke_l7_rilb_gateway_yaml.content_sha512}",
        "${local_file.hello_world_deployment_yaml.content_sha512}",
        "${local_file.hello_world_http_route_gke_l7_global_external_managed_yaml.content_sha512}",
        "${local_file.hello_world_http_route_gke_l7_regional_external_managed_yaml.content_sha512}",
        "${local_file.hello_world_http_route_gke_l7_rilb_yaml.content_sha512}",
      ]
    )
  )
}
