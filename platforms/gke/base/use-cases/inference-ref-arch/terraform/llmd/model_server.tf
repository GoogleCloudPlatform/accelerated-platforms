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

#Create a SecretProviderClass for Huggingface token
resource "local_file" "llmd_spc_yaml" {
  content = templatefile(
    "${path.module}/templates/workload/secretproviderclass-huggingface-tokens.tftpl.yaml",
    {
      huggingface-token-spc                                        = var.llmd_huggingface_spc
      namespace                                                    = var.llmd_kubernetes_namespace
      huggingface-secret-manager-project-id                        = local.huggingface_hub_models_bucket_project_id
      huggingface-hub-access-token-read-secret-manager-secret-name = local.huggingface_hub_access_token_read_secret_manager_secret_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/secretproviderclass.yaml"
}

module "kubectl_apply_llmd_spc" {
  depends_on = [
    local_file.llmd_spc_yaml,
    module.kubectl_apply_llmd_gaie_manifests
  ]
  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/secretproviderclass.yaml"
  manifest_includes_namespace = true
}

#Create Service Account for model server
resource "local_file" "llmd_ms_sa_yaml" {
  content = templatefile(
    "${path.module}/templates/workload/llmd_model_server_sa.tpl.yaml",
    {
      serviceaccount-name = local.llmd_modelserver_sa
      namespace           = var.llmd_kubernetes_namespace
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/modelserver_sa.yaml"
}

module "kubectl_apply_llmd_ms_sa" {
  depends_on = [
    local_file.llmd_ms_sa_yaml,
    module.kubectl_apply_llmd_spc
  ]
  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/modelserver_sa.yaml"
  manifest_includes_namespace = true
}

resource "google_project_iam_member" "workload_identity_secret_access" {
  depends_on = [module.kubectl_apply_llmd_ms_sa]
  member     = "${local.workload_identity_principal_prefix}/ns/${var.llmd_kubernetes_namespace}/sa/${local.llmd_modelserver_sa}"
  project    = data.google_project.cluster.project_id
  role       = "roles/secretmanager.secretAccessor"
}

#Create Deployment for model server
resource "local_file" "llmd_ms_yaml" {
  content = templatefile(
    "${path.module}/templates/workload/llmd_model_server_deployment_${var.llmd_accelerator_type}.tpl.yaml",
    {
      deployment_name       = "${local.llmd_ms_deployment_name}-${var.llmd_accelerator_type}"
      namespace             = var.llmd_kubernetes_namespace
      routing_proxy_image   = var.llmd_ms_proxy_image
      serviceaccount_name   = local.llmd_modelserver_sa
      huggingface_token_spc = var.llmd_huggingface_spc
      cuda_image            = var.llmd_ms_cuda_image
      model_name            = var.llmd_model_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/modelserver_deployment.yaml"
}

module "kubectl_apply_llmd_ms" {
  depends_on = [
    local_file.llmd_ms_yaml,
    module.kubectl_apply_llmd_ms_sa
  ]
  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/model_server/modelserver_deployment.yaml"
  manifest_includes_namespace = true
}
