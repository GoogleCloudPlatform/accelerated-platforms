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

resource "null_resource" "kueue_manifests" {
  provisioner "local-exec" {
    command     = <<EOT
mkdir -p ${self.triggers.manifests_dir}
wget https://github.com/kubernetes-sigs/kueue/releases/download/v${self.triggers.version}/manifests.yaml -O ${self.triggers.manifests_dir}/manifests.yaml
cp -r manifests/* ${self.triggers.manifests_dir}/
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.triggers.manifests_dir}"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers = {
    always_run    = timestamp()
    manifests_dir = "${local.manifests_directory}/kueue-${var.kueue_version}"
    version       = var.kueue_version
  }
}

resource "null_resource" "kueue_manifests_apply" {
  depends_on = [
    null_resource.cluster_credentials,
    null_resource.kueue_manifests,
  ]

  provisioner "local-exec" {
    command = "kubectl apply --server-side --kustomize ${self.triggers.manifests_dir}"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command = "kubectl delete --kustomize ${self.triggers.manifests_dir}; exit 0"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers = {
    kubeconfig_file = local.kubeconfig_file
    manifests_dir   = "${local.manifests_directory}/kueue-${var.kueue_version}"
    version         = var.kueue_version
  }
}

resource "google_monitoring_dashboard" "kueue_monitoring_dashboard" {
  dashboard_json = file("${path.module}/dashboards/kueue-monitoring-dashboard.json")
  project        = data.google_project.default.project_id
}
