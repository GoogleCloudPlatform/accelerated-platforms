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
  deployment_name          = "workflow-api"
  comfyui_service_name     = "comfyui-nvidia-l4"
  manifests_directory      = "${local.manifests_directory_root}/${local.deployment_name}"
  manifests_directory_root = "${path.module}/../../../../kubernetes/manifests"
  kubeconfig_directory     = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file          = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
}

provider "kubernetes" {
  config_path = local.kubeconfig_file
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "workload" {
  depends_on = [
    terraform_data.submit_docker_build,
  ]

  content = templatefile(
    "${path.module}/templates/workflow-api-deployment.tftpl.yaml",
    {
      image_name           = local.image_destination
      deployment_name      = local.deployment_name
      namespace            = var.comfyui_kubernetes_namespace
      comfyui_service_name = local.comfyui_service_name
      service_account      = local.workflow_api_serviceaccount
    }
  )
  filename = "${local.manifests_directory}/${local.deployment_name}-deployment.yaml"
}

module "kubectl_apply_workload_manifest" {
  depends_on = [
    local_file.workload,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.workload.filename
  manifest_includes_namespace = false
  namespace                   = var.comfyui_kubernetes_namespace
}


