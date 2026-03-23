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
      namespace                                                    = local.ira_online_gpu_kubernetes_namespace_name
      huggingface-secret-manager-project-id                        = local.huggingface_hub_models_bucket_project_id
      huggingface-hub-access-token-read-secret-manager-secret-name = local.huggingface_hub_access_token_read_secret_manager_secret_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${local.ira_online_gpu_kubernetes_namespace_name}/model_server/secretproviderclass.yaml"
}

module "kubectl_apply_llmd_spc" {
  depends_on = [
    local_file.llmd_spc_yaml,
    module.kubectl_apply_llmd_gaie_manifests
  ]
  source = "../../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${local.ira_online_gpu_kubernetes_namespace_name}/model_server/secretproviderclass.yaml"
  manifest_includes_namespace = true
}
