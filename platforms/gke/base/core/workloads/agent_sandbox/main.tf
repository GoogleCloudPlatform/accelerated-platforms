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
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory                 = "${local.namespace_directory}/${local.namespace}"
  namespace                           = "agent-sandbox"
  namespace_directory                 = "${local.manifests_directory_root}/namespace"
  template_manifests_directory        = "${path.module}/manifests/agent_sandbox"
  template_manifests_source_directory = "${path.module}/templates/manifests"

  template_manifests_source_directory_contents_hash = sha512(join("", [for f in fileset(local.template_manifests_source_directory, "**") : filesha512("${local.template_manifests_source_directory}/${f}")]))
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

module "kubectl_wait_crds" {
  for_each = toset(var.cluster_addons_agent_sandbox_enabled ? [
    "crd/sandboxes.agents.x-k8s.io",
    "crd/sandboxclaims.extensions.agents.x-k8s.io",
    "crd/sandboxtemplates.extensions.agents.x-k8s.io",
    "crd/sandboxwarmpools.extensions.agents.x-k8s.io",
  ] : [])

  source = "../../../modules/kubectl_wait"

  for              = "condition=established"
  kubeconfig_file  = data.local_file.kubeconfig.filename
  resource         = each.key
  retry_on_failure = true
  timeout          = "300s"
  wait_for_create  = true
}

resource "terraform_data" "namespace" {
  for_each = toset(var.cluster_addons_agent_sandbox_enabled ? ["namespace"] : [])

  input = {
    manifests_dir = local.namespace_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.manifests_dir}" && \
cp -r templates/namespace-agent-sandbox.yaml "${self.input.manifests_dir}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.input.manifests_dir}/namespace-agent-sandbox.yaml"
    interpreter = ["bash", "-c"]
    when        = destroy
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

  for_each = toset(var.cluster_addons_agent_sandbox_enabled ? ["namespace"] : [])

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  delete_ignore_not_found     = true
  delete_timeout              = "300s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/namespace-agent-sandbox.yaml"
  manifest_includes_namespace = true
}

resource "terraform_data" "manifests" {
  depends_on = [
    module.kubectl_apply_namespace,
  ]

  for_each = toset(var.cluster_addons_agent_sandbox_enabled ? ["manifests"] : [])

  input = {
    manifests_directory                 = local.manifests_directory
    template_manifests_directory        = local.template_manifests_directory
    template_manifests_source_directory = local.template_manifests_source_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p "${self.input.template_manifests_directory}" && \
mkdir -p "${self.input.manifests_directory}" && \
cp -r "${self.input.template_manifests_source_directory}"/* "${self.input.template_manifests_directory}/" && \
cp -r "${self.input.template_manifests_directory}"/* "${self.input.manifests_directory}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = <<EOT
rm -rf "${self.input.manifests_directory}" "${self.input.template_manifests_directory}"
EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    manifests_directory                               = local.manifests_directory
    template_manifests_directory                      = local.template_manifests_directory
    template_manifests_source_directory_contents_hash = local.template_manifests_source_directory_contents_hash
  }
}

module "kubectl_apply_manifests" {
  depends_on = [
    module.kubectl_apply_namespace,
    module.kubectl_wait_crds,
    terraform_data.manifests,
  ]

  for_each = toset(var.cluster_addons_agent_sandbox_enabled ? ["manifests"] : [])

  source = "../../../modules/kubectl_apply"

  apply_once                  = false
  apply_server_side           = true
  delete_ignore_not_found     = true
  delete_timeout              = "300s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.template_manifests_directory
  manifest_includes_namespace = true
  recursive                   = true
  source_content_hash         = local.template_manifests_source_directory_contents_hash
  use_kustomize               = false
}
