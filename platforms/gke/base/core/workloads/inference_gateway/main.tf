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
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  crd_manifests_directory     = "${local.manifests_directory_root}/cluster/crds/gateway-api-inference-extension"
  gmp_kubernetes_namespace    = var.cluster_autopilot_enabled ? "gke-gmp-system" : "gmp-system"
  kubernetes_namespace        = var.inference_gateway_kubernetes_namespace
  manifests_directory         = "${local.namespace_directory}/${local.kubernetes_namespace}"
  default_namespace_directory = "${local.namespace_directory}/default"
  namespace_directory         = "${local.manifests_directory_root}/namespace"
  version_manifests_directory = "${path.module}/manifests/gateway-api-inference-extension-${var.inference_gateway_version}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

# CRDs
###############################################################################
resource "terraform_data" "crd_manifests" {
  input = {
    manifests_dir         = local.crd_manifests_directory
    version               = var.inference_gateway_version
    version_manifests_dir = local.version_manifests_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p ${self.input.version_manifests_dir} && \
mkdir -p ${self.input.manifests_dir} && \
wget https://github.com/kubernetes-sigs/gateway-api-inference-extension/raw/v${self.input.version}/config/crd/bases/inference.networking.x-k8s.io_inferenceobjectives.yaml -O ${self.input.version_manifests_dir}/inference.networking.x-k8s.io_inferenceobjectives.yaml && \
cp -r ${self.input.version_manifests_dir}/* ${self.input.manifests_dir}/
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir         = local.crd_manifests_directory
    version               = var.inference_gateway_version
    version_manifests_dir = local.version_manifests_directory
  }
}

module "kubectl_apply_crd_manifests" {
  depends_on = [
    terraform_data.crd_manifests,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.version_manifests_directory
  manifest_includes_namespace = true
  use_kustomize               = false
}



# Namespace
###############################################################################
# resource "local_file" "namespace_yaml" {
#   content = templatefile(
#     "${path.module}/templates/namespace.yaml",
#     {
#       kubernetes_namespace = local.kubernetes_namespace
#     }
#   )
#   file_permission = "0644"
#   filename        = "${local.namespace_directory}/namespace-${local.kubernetes_namespace}.yaml"
# }

# module "kubectl_apply_namespace" {
#   depends_on = [
#     local_file.namespace_yaml,
#   ]

#   source = "../../../modules/kubectl_apply"

#   delete_timeout              = "60s"
#   error_on_delete_failure     = false
#   kubeconfig_file             = data.local_file.kubeconfig.filename
#   manifest                    = "${local.namespace_directory}/namespace-${local.kubernetes_namespace}.yaml"
#   manifest_includes_namespace = true
# }



# Manifests
###############################################################################
resource "local_file" "metrics_yaml" {
  content = templatefile(
    "${path.module}/templates/workload/metrics.yaml",
    {
      gmp_kubernetes_namespace = local.gmp_kubernetes_namespace
      kubernetes_namespace     = "default"
    }
  )
  file_permission = "0644"
  filename        = "${local.default_namespace_directory}/inference-gateway-gmp-metrics.yaml"
}

module "kubectl_apply_manifests" {
  depends_on = [
    local_file.metrics_yaml,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.default_namespace_directory}/inference-gateway-gmp-metrics.yaml"
  manifest_includes_namespace = true
}
