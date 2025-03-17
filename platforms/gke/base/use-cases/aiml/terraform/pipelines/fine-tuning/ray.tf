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
  ray_cluster_manifests_directory         = "${local.fine_tuning_team_namespace_manifests_directory}/ray-cluster"
  ray_cluster_templates_directory         = "${path.module}/templates/ray/ray-clusters/${local.ray_operator_type}"
  ray_cluster_version_manifests_directory = "${path.module}/manifests/workload/ray-cluster-${local.ray_helm_ray_cluster_chart_version}"
  ray_operator_type                       = var.cluster_addons_ray_operator_enabled ? "managed" : "self-managed"
  ray_helm_ray_cluster_chart_version      = "1.3.0"

}

data "helm_template" "ray_cluster" {
  chart      = "ray-cluster"
  name       = "ray-cluster"
  namespace  = var.fine_tuning_team_namespace
  repository = "https://ray-project.github.io/kuberay-helm/"
  version    = local.ray_helm_ray_cluster_chart_version

  values = [
    templatefile(
      "${local.ray_cluster_templates_directory}/ray-cluster-values.tftpl.yaml",
      {}
    )
  ]
}

resource "terraform_data" "ray_cluster_manifests_dir" {
  depends_on = [
    module.kubectl_apply_namespace_manifest
  ]

  input = {
    manifests_dir         = local.ray_cluster_manifests_directory
    templates_dir         = local.ray_cluster_templates_directory
    version_manifests_dir = local.ray_cluster_version_manifests_directory
    version               = local.ray_helm_ray_cluster_chart_version
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.version_manifests_dir}" && \
cp -r ${self.input.templates_dir}/workload/* "${self.input.version_manifests_dir}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.input.version_manifests_dir}"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir         = local.ray_cluster_manifests_directory
    templates_dir         = local.ray_cluster_templates_directory
    version_manifests_dir = local.ray_cluster_version_manifests_directory
    version               = local.ray_helm_ray_cluster_chart_version
  }
}

resource "local_file" "ray_cluster_manifests" {
  depends_on = [
    terraform_data.ray_cluster_manifests_dir,
  ]

  filename = "${local.ray_cluster_version_manifests_directory}/manifests.yaml"
  content  = data.helm_template.ray_cluster.manifest
}

resource "terraform_data" "ray_cluster_manifests" {
  depends_on = [
    local_file.ray_cluster_manifests
  ]

  input = {
    manifests_dir         = local.ray_cluster_manifests_directory
    version_manifests_dir = local.ray_cluster_version_manifests_directory
    version               = local.ray_helm_ray_cluster_chart_version
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.manifests_dir}" && \
cp -r "${self.input.version_manifests_dir}"/* "${self.input.manifests_dir}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.input.manifests_dir}"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir         = local.ray_cluster_manifests_directory
    version_manifests_dir = local.ray_cluster_version_manifests_directory
    version               = local.ray_helm_ray_cluster_chart_version
  }
}

module "kubectl_apply_ray_cluster_manifest" {
  depends_on = [
    terraform_data.ray_cluster_manifests,
  ]

  source = "../../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.ray_cluster_manifests_directory
  manifest_includes_namespace = false
  namespace                   = var.fine_tuning_team_namespace
}
