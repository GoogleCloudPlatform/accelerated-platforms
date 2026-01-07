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
  external_gateway_manifests_directory = "${local.manifests_directory}/external-gateway"
  gaie_values                          = yamldecode(file("${path.module}/helm_values/gaie_values.yaml"))
  gradio_backend_service_regex         = ".*${var.llm-d_kubernetes_namespace}-${local.gradio_service_name}-${local.gradio_service_port}-.*"
  gradio_service_name                  = "gradio-svc"
  gradio_service_port                  = 8080
  iap_domain                           = var.llm-d_iap_domain != null ? var.llm-d_iap_domain : split("@", trimspace(data.google_client_openid_userinfo.identity.email))[1]
  iap_oath_brand                       = "projects/${data.google_project.llm-d_iap_oath_branding.number}/brands/${data.google_project.llm-d_iap_oath_branding.number}"
  internal_gateway_manifests_directory = "${local.manifests_directory}/internal-gateway"
  kubeconfig_directory                 = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file                      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  llm-d_endpoint                       = local.llm-d_endpoints_hostname
  manifests_directory                  = "${local.namespace_directory}/${var.llm-d_kubernetes_namespace}"
  manifests_directory_root             = "${path.module}/../../../../kubernetes/manifests"
  namespace_directory                  = "${local.manifests_directory_root}/namespace"
  workload_identity_principal_prefix   = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
}

data "google_client_openid_userinfo" "identity" {}

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

# Create Namespace
resource "local_file" "namespace_yaml" {
  content = templatefile(
    "${path.module}/templates/namespace/namespace.tftpl.yaml",
    {
      kubernetes_namespace = var.llm-d_kubernetes_namespace
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/namespace-${var.llm-d_kubernetes_namespace}.yaml"
}

module "kubectl_apply_namespace" {
  depends_on = [
    local_file.namespace_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/namespace-${var.llm-d_kubernetes_namespace}.yaml"
  manifest_includes_namespace = true
}
