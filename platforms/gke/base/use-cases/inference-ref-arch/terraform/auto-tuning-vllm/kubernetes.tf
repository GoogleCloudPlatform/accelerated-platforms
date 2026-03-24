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
  cluster_wi_principal_prefix                         = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  ira_auto_tuning_vllm_ksa_member                     = "${local.cluster_wi_principal_prefix}/ns/${local.ira_auto_tuning_vllm_kubernetes_namespace_name}/sa/${local.ira_auto_tuning_vllm_kubernetes_service_account_name}"
  ira_auto_tuning_vllm_kubernetes_namespace_directory = "${local.namespaces_directory}/${local.ira_auto_tuning_vllm_kubernetes_namespace_name}"
  kubeconfig_directory                                = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file                                     = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  manifests_directory_root                            = "${path.module}/../../../../kubernetes/manifests"
  namespaces_directory                                = "${local.manifests_directory_root}/namespace"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

# Create Namespace
resource "local_file" "namespace_yaml" {
  content = templatefile(
    "${path.module}/templates/namespace/namespace.tftpl.yaml",
    {
      kubernetes_namespace = local.ira_auto_tuning_vllm_kubernetes_namespace_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/namespace-${local.ira_auto_tuning_vllm_kubernetes_namespace_name}.yaml"
}

module "kubectl_apply_namespace" {
  depends_on = [
    local_file.namespace_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/namespace-${var.llmd_kubernetes_namespace}.yaml"
  manifest_includes_namespace = true
}


resource "local_file" "serviceaccount_yaml" {
  content = templatefile(
    "${path.module}/templates/kubernetes/serviceaccount.tftpl.yaml",
    {
      name      = local.ira_auto_tuning_vllm_kubernetes_service_account_name
      namespace = local.ira_auto_tuning_vllm_kubernetes_namespace_name
    }
  )
  filename = "${local.ira_auto_tuning_vllm_kubernetes_namespace_directory}/serviceaccount-${local.ira_auto_tuning_vllm_kubernetes_service_account_name}.yaml"
}

module "kubectl_apply_service_account" {
  source = "../../../../modules/kubectl_apply"
  depends_on = [
    local_file.serviceaccount_yaml, kubectl_apply_namespace
  ]

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.ira_auto_tuning_vllm_kubernetes_namespace_directory}/serviceaccount-${local.ira_auto_tuning_vllm_kubernetes_service_account_name}.yaml"
  manifest_includes_namespace = true
}

resource "local_file" "secretproviderclass_yaml" {
  content = templatefile(
    "${path.module}/templates/kubernetes/secretproviderclass.tftpl.yaml",
    {
      namespace                = local.ira_auto_tuning_vllm_kubernetes_namespace_name
      project_id               = data.google_secret_manager_secret.hub_access_token_read.project
      secretproviderclass_name = local.ira_auto_tuning_vllm_secretprovider
      secret_name              = local.huggingface_hub_access_token_read_secret_manager_secret_name

    }
  )
  filename = "${local.ira_auto_tuning_vllm_kubernetes_namespace_directory}/secretproviderclass-${local.ira_auto_tuning_vllm_secretprovider}.yaml"
}

module "kubectl_apply_secretproviderclass" {
  source = "../../../../modules/kubectl_apply"
  depends_on = [
    local_file.secretproviderclass_yaml, kubectl_apply_namespace
  ]

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.ira_auto_tuning_vllm_kubernetes_namespace_directory}/secretproviderclass-${local.ira_auto_tuning_vllm_secretprovider}.yaml"
  manifest_includes_namespace = true
}
