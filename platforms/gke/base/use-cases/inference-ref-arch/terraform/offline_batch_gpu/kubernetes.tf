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
  kubeconfig_directory = "${path.module}/../../../../kubernetes/kubeconfig/"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  workloads = {
    ira_offline_batch_gpu = {
      directory       = "${local.namespaces_directory}/${local.ira_offline_batch_gpu_kubernetes_namespace_name}"
      namespace       = local.ira_offline_batch_gpu_kubernetes_namespace_name
      service_account = local.ira_offline_batch_gpu_kubernetes_service_account_name
    }
    ira_offline_batch_cpu_dataset_downloader = {
      directory       = "${local.namespaces_directory}/${local.ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name}"
      namespace       = local.ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name
      service_account = local.ira_offline_batch_cpu_dataset_downloader_kubernetes_service_account_name
    }
    ira_offline_batch_cpu_worker = {
      directory       = "${local.namespaces_directory}/${local.ira_offline_batch_cpu_worker_kubernetes_namespace_name}"
      namespace       = local.ira_offline_batch_cpu_worker_kubernetes_namespace_name
      service_account = local.ira_offline_batch_cpu_worker_kubernetes_service_account_name
    }
  }

  manifests_directory_root = "${path.module}/../../../../kubernetes/manifests"
  namespaces_directory     = "${local.manifests_directory_root}/namespace"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "namespace_yaml" {
  for_each = local.workloads
  content = templatefile(
    "${path.module}/templates/kubernetes/namespace.tftpl.yaml",
    {
      name = each.value.namespace
    }
  )
  filename = "${local.namespaces_directory}/namespace-${each.value.namespace}.yaml"
}

module "kubectl_apply_namespace" {
  for_each = local.workloads
  depends_on = [
    local_file.namespace_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_server_side           = true
  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespaces_directory}/namespace-${each.value.namespace}.yaml"
  manifest_includes_namespace = true
}

resource "local_file" "serviceaccount_yaml" {
  for_each = local.workloads
  content = templatefile(
    "${path.module}/templates/kubernetes/serviceaccount.tftpl.yaml",
    {
      name      = each.value.service_account
      namespace = each.value.namespace
    }
  )
  filename = "${each.value.directory}/serviceaccount-${each.value.service_account}.yaml"
}

module "kubectl_apply_service_account" {
  for_each = local.workloads
  depends_on = [
    local_file.serviceaccount_yaml,
    module.kubectl_apply_namespace,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${each.value.directory}/serviceaccount-${each.value.service_account}.yaml"
  manifest_includes_namespace = true
}
