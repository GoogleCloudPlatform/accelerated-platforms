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
  kubectl_delete_error_on_failure = var.error_on_delete_failure ? "" : "; exit 0"
  kubectl_apply_server_side       = var.apply_server_side ? "--server-side " : ""
  kubectl_manifest_option         = var.use_kustomize ? "--kustomize=" : "--filename="
  kubectl_namespace               = var.manifest_includes_namespace ? "" : "--namespace=${var.namespace} "
  kubectl_recursive               = var.recursive ? " --recursive" : ""

  kubectl_apply_command  = "kubectl ${local.kubectl_namespace}apply ${local.kubectl_apply_server_side}${local.kubectl_manifest_option}${var.manifest}${local.kubectl_recursive}"
  kubectl_delete_command = var.manifest_can_be_updated ? "" : "kubectl ${local.kubectl_namespace}delete ${local.kubectl_manifest_option}${var.manifest}${local.kubectl_recursive}${local.kubectl_delete_error_on_failure}"

  manifest_is_directory = try(provider::local::direxists(var.manifest), false)
}

data "local_file" "kubeconfig" {
  filename = var.kubeconfig_file
}

resource "terraform_data" "manifest" {
  input = {
    kubeconfig_file        = data.local_file.kubeconfig.filename
    kubectl_apply_command  = local.kubectl_apply_command
    kubectl_delete_command = local.kubectl_delete_command
  }

  provisioner "local-exec" {
    command = self.input.kubectl_apply_command
    environment = {
      KUBECONFIG = self.input.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    working_dir = path.root
  }

  provisioner "local-exec" {
    command = self.input.kubectl_delete_command
    environment = {
      KUBECONFIG = self.input.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.root
  }

  triggers_replace = {
    kubeconfig_file        = data.local_file.kubeconfig.filename
    kubectl_apply_command  = local.kubectl_apply_command
    kubectl_delete_command = local.kubectl_delete_command
    source_content_hash    = var.apply_once ? "" : var.source_content_hash
  }
}
