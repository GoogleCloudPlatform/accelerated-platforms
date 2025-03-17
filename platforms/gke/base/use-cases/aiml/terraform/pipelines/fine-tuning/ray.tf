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
  #gcloud container clusters describe aiml-dev --project rueth-dev --location us-central1 --format"=value(addonsConfig.rayOperatorConfig.enabled)
  #True
  fine_tuning_ray_operator_type               = "managed"
  kuberay_helm_kuberay_operator_chart_version = "1.3.0"
  kuberay_helm_ray_cluster_chart_version      = "1.3.0"
}

# TODO: Move to core/workloads
# data "helm_template" "kuberay_operator" {
#   chart            = "kuberay-operator"
#   create_namespace = true
#   name             = "kuberay-operator"
#   namespace        = "default"
#   repository       = "https://ray-project.github.io/kuberay-helm/"
#   version          = local.kuberay_helm_kuberay_operator_chart_version

#   values = [
#     templatefile(
#       "${path.module}/templates/ray/kuberay-operator/kuberay-operator-values.tftpl.yaml",
#       {
#         image_tag = "v${local.kuberay_helm_kuberay_operator_chart_version}"
#       }
#     )
#   ]
# }

# resource "local_file" "kuberay_operator_manifests" {
#   for_each = data.helm_template.kuberay_operator.manifests

#   filename = "${local.fine_tuning_manifests_directory}/namespace/kuberay/operator/${basename(each.key)}"
#   content  = each.value
# }

data "helm_template" "ray_cluster" {
  chart      = "ray-cluster"
  name       = "ray-cluster"
  namespace  = var.fine_tuning_namespace
  repository = "https://ray-project.github.io/kuberay-helm/"
  version    = local.kuberay_helm_ray_cluster_chart_version

  values = [
    templatefile(
      "${path.module}/templates/ray/ray-clusters/${local.fine_tuning_ray_operator_type}/ray-cluster-values.tftpl.yaml",
      {}
    )
  ]
}

resource "local_file" "ray_cluster_manifests" {
  for_each = data.helm_template.ray_cluster.manifests

  filename = "${local.fine_tuning_manifests_directory}/namespace/${var.fine_tuning_namespace}/ray/${basename(each.key)}"
  content  = each.value
}

module "kubectl_apply_ray_cluster_manifest" {
  source = "../../../../../modules/kubectl_apply"

  for_each = local_file.ray_cluster_manifests

  kubeconfig_file = data.local_file.kubeconfig.filename
  manifest        = local_file.ray_cluster_manifests[each.key].filename
  namespace       = var.fine_tuning_namespace
}
