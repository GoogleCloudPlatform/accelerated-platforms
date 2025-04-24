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

  manifests_directory         = "${local.namespace_directory}/custom-metrics"
  namespace_directory         = "${local.manifests_directory_root}/namespace"
  version_manifests_directory = "${path.module}/manifests/cma-${var.custom_metrics_adapter_version}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "terraform_data" "namespace" {
  input = {
    manifests_dir = local.namespace_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.manifests_dir}" && \
cp -r templates/namespace-custom-metrics.yaml "${self.input.manifests_dir}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir = local.namespace_directory
  }
}

module "kubectl_apply_namespace" {
  depends_on = [
    terraform_data.namespace,
  ]

  source = "../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/namespace-custom-metrics.yaml"
  manifest_includes_namespace = true
}

resource "terraform_data" "manifests" {
  input = {
    manifests_dir         = local.manifests_directory
    version_manifests_dir = local.version_manifests_directory
    version               = var.custom_metrics_adapter_version
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.version_manifests_dir}" && \
mkdir -p "${self.input.manifests_dir}" && \
wget https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/cm-sd-adapter-v${self.input.version}/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml -O "${self.input.version_manifests_dir}/manifests.yaml" && \
cp -r templates/workload/* "${self.input.version_manifests_dir}/" && \
cp -r "${self.input.version_manifests_dir}"/* "${self.input.manifests_dir}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir         = local.manifests_directory
    version_manifests_dir = local.version_manifests_directory
    version               = var.custom_metrics_adapter_version
  }
}

module "kubectl_apply_manifests" {
  depends_on = [
    terraform_data.manifests,
    module.kubectl_apply_namespace,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.version_manifests_directory
  manifest_includes_namespace = true
  use_kustomize               = true
}
