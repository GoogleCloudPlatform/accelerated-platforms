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

locals {
  kubeconfig_directory = "${path.module}/../../../_shared_config/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory         = "${local.manifests_directory_root}/namespace/kueue-system"
  namespace_directory         = "${local.manifests_directory_root}/namespace"
  version_manifests_directory = "${path.module}/manifests/kueue-${var.kueue_version}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "null_resource" "namespace" {
  provisioner "local-exec" {
    command     = <<EOT
mkdir -p ${self.triggers.manifests_dir} && \
cp -r templates/namespace-kueue-system.yaml ${self.triggers.manifests_dir}/
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers = {
    manifests_dir = local.namespace_directory
  }
}

module "kubectl_apply_namespace" {
  depends_on = [
    null_resource.namespace,
  ]

  source = "../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/namespace-kueue-system.yaml"
  manifest_includes_namespace = true
}

resource "null_resource" "manifests" {
  provisioner "local-exec" {
    command     = <<EOT
mkdir -p ${self.triggers.version_manifests_dir} && \
mkdir -p ${self.triggers.manifests_dir} && \
wget https://github.com/kubernetes-sigs/kueue/releases/download/v${self.triggers.version}/manifests.yaml -O ${self.triggers.version_manifests_dir}/manifests.yaml && \
cp -r templates/workload/* ${self.triggers.version_manifests_dir}/ && \
cp -r ${self.triggers.version_manifests_dir}/* ${self.triggers.manifests_dir}/
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers = {
    manifests_dir         = local.manifests_directory
    version_manifests_dir = local.version_manifests_directory
    version               = var.kueue_version
  }
}

module "kubectl_apply_manifests" {
  depends_on = [
    null_resource.manifests,
    module.kubectl_apply_namespace,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.version_manifests_directory
  manifest_includes_namespace = true
  use_kustomize               = true
}

resource "google_monitoring_dashboard" "kueue_monitoring_dashboard" {
  dashboard_json = file("${path.module}/dashboards/kueue-monitoring-dashboard.json")
  project        = data.google_project.default.project_id

  lifecycle {
    ignore_changes = [
      dashboard_json
    ]
  }
}
