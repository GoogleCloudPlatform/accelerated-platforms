# Copyright 2026 Google LLC
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
  kubeconfig_directory = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  namespaces_directory = "${local.manifests_directory_root}/namespaces"

  workloads = {
    rl_cpu_mlflow = {
      directory       = "${local.namespaces_directory}/${local.rl_cpu_mlflow_kubernetes_namespace_name}"
      namespace       = local.rl_cpu_mlflow_kubernetes_namespace_name
      service_account = local.rl_cpu_mlflow_kubernetes_service_account_name
    }
    rl_tpu_maxtext_grpo_multi_host = {
      directory       = "${local.namespaces_directory}/${local.rl_tpu_maxtext_grpo_multi_host_kubernetes_namespace_name}"
      namespace       = local.rl_tpu_maxtext_grpo_multi_host_kubernetes_namespace_name
      service_account = local.rl_tpu_maxtext_grpo_multi_host_kubernetes_service_account_name
    }
  }
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "terraform_data" "namespaces" {
  for_each = local.workloads

  input = {
    directory       = each.value.directory
    namespace       = each.value.namespace
    service_account = each.value.service_account
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.directory}" && \
cp -r templates/kubernetes/* "${self.input.directory}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    directory       = each.value.directory
    namespace       = each.value.namespace
    service_account = each.value.service_account
  }
}

resource "local_file" "namespace" {
  for_each = local.workloads

  content = templatefile(
    "${path.module}/templates/kubernetes/namespace.tftpl.yaml",
    {
      namespace = each.value.namespace,
    }
  )
  filename = "${each.value.directory}/namespace.yaml"
}

resource "local_file" "service_account" {
  for_each = local.workloads

  content = templatefile(
    "${path.module}/templates/kubernetes/serviceaccount.tftpl.yaml",
    {
      namespace            = each.value.namespace,
      service_account_name = each.value.service_account,
    }
  )
  filename = "${each.value.directory}/service-account.yaml"
}

module "kubectl_apply_namespace" {
  depends_on = [
    terraform_data.namespaces,
    local_file.namespace,
  ]

  for_each = local.workloads

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${each.value.directory}/namespace.yaml"
  manifest_includes_namespace = false
}

module "kubectl_apply_service_account" {
  depends_on = [
    module.kubectl_apply_namespace,
    local_file.service_account,
  ]

  for_each = local.workloads

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${each.value.directory}/service-account.yaml"
  manifest_includes_namespace = true
}
