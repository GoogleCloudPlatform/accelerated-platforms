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
  comfyui_service_name = "${var.comfyui_app_name}-${var.comfyui_accelerator_type}"
  deployment_name      = "workflow-api"
  iap_configmap_name   = "${local.deployment_name}-iap-config"

  kubeconfig_directory = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory_root      = "${path.module}/../../../../kubernetes/manifests"
  namespace_directory           = "${local.manifests_directory_root}/namespace"
  namespace_manifests_directory = "${local.namespace_directory}/${var.comfyui_kubernetes_namespace}"
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
      allowed_auth_domain  = var.workflow_api_allowed_auth_domain
      comfyui_service_name = local.comfyui_service_name
      deployment_name      = local.deployment_name
      google_client_id     = var.workflow_api_google_client_id
      iap_configmap_name   = local.iap_configmap_name
      image_name           = local.image_destination
      namespace            = var.comfyui_kubernetes_namespace
      service_account      = local.workflow_api_serviceaccount
    }
  )
  filename = "${local.namespace_manifests_directory}/${local.deployment_name}-deployment.yaml"
}

module "kubectl_apply_workload_manifest" {
  depends_on = [
    local_file.workload,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.workload.filename
  manifest_includes_namespace = true
}
