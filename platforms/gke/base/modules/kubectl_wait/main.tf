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
  kubectl_wait_filename  = var.filename != null ? " --filename=${var.filename}" : ""
  kubectl_wait_namespace = var.namespace != null ? " --namespace=${var.namespace}" : " --all-namespaces"
  kubectl_wait_resource  = var.resource != null ? " ${var.resource}" : ""
  kubectl_wait_retry     = var.retry_on_failure
  kubectl_wait_selector  = var.selector != null ? " --selector=${var.selector}" : ""

  kubectl_wait_command            = "kubectl wait --for='${var.for}'${local.kubectl_wait_namespace} --timeout=${var.timeout}${local.kubectl_wait_resource}${local.kubectl_wait_selector}${local.kubectl_wait_filename}"
  kubectl_wait_for_create_command = var.wait_for_create ? "kubectl wait --for=create${local.kubectl_wait_namespace} --timeout=${var.timeout}${local.kubectl_wait_resource}${local.kubectl_wait_selector}${local.kubectl_wait_filename}" : ":"
}

data "local_file" "kubeconfig" {
  filename = var.kubeconfig_file
}

resource "terraform_data" "manifest" {
  input = {
    kubeconfig_file                 = data.local_file.kubeconfig.filename
    kubectl_wait_retry              = local.kubectl_wait_retry
    kubectl_wait_command            = local.kubectl_wait_command
    kubectl_wait_for_create_command = local.kubectl_wait_for_create_command
  }

  provisioner "local-exec" {
    command = <<EOT
${self.input.kubectl_wait_for_create_command} &&
${self.input.kubectl_wait_command}
return_code=$?
if ${self.input.kubectl_wait_retry} && [[ $${return_code} != 0 ]]; then
  sleep 1
  echo "Retrying..."
  ${self.input.kubectl_wait_for_create_command} &&
  ${self.input.kubectl_wait_command}
fi
EOT
    environment = {
      KUBECONFIG = self.input.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    working_dir = path.root
  }
}
