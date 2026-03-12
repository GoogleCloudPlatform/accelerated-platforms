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
  kubeconfig_directory = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory                          = "${path.module}/../../../../kubernetes/manifests"
  manifests_namespace_directory                = "${local.manifests_directory}/namespace"
  mft_kubernetes_namespace_manifests_directory = "${local.manifests_namespace_directory}/${local.mft_kubernetes_namespace}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

provider "kubernetes" {
  #cluster_ca_certificate = base64decode(data.google_container_cluster.cluster.master_auth[0].cluster_ca_certificate)
  host     = "https://${data.google_container_cluster.cluster.control_plane_endpoints_config[0].dns_endpoint_config[0].endpoint}"
  insecure = true
  token    = data.google_client_config.default.access_token
}

resource "local_file" "kubernetes_namespace" {
  content = templatefile(
    "${path.module}/templates/kubernetes/namespace.tftpl.yaml",
    {
      namespace_name = local.mft_kubernetes_namespace,
    }
  )
  filename = "${local.manifests_namespace_directory}/namespace-${local.mft_kubernetes_namespace}.yaml"
}

resource "local_file" "kubernetes_service_account" {
  for_each = local.mft_kubernetes_service_accounts

  content = templatefile(
    "${path.module}/templates/kubernetes/service-account.tftpl.yaml",
    {
      automount_service_account_token = each.value.automount_service_account_token,
      service_account_name            = each.value.service_account_name,
    }
  )
  filename = "${local.mft_kubernetes_namespace_manifests_directory}/service-account-${each.key}.yaml"
}

module "kubectl_apply_namespace_manifest" {
  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.kubernetes_namespace.filename
  manifest_includes_namespace = true
}

module "kubectl_apply_service_account_manifest" {
  depends_on = [
    module.kubectl_apply_namespace_manifest,
  ]
  source = "../../../../modules/kubectl_apply"

  for_each = local.mft_kubernetes_service_accounts

  kubeconfig_file = data.local_file.kubeconfig.filename
  manifest        = local_file.kubernetes_service_account[each.key].filename
  namespace       = local.mft_kubernetes_namespace
}
