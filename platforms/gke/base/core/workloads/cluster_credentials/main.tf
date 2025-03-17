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
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
}

resource "terraform_data" "cluster_credentials" {
  input = {
    cluster_credentials_command = local.cluster_credentials_command
    kubeconfig_file             = local.kubeconfig_file
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p $(dirname ${self.input.kubeconfig_file})
KUBECONFIG=${self.input.kubeconfig_file} ${self.input.cluster_credentials_command} 
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.input.kubeconfig_file}"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    always_run = timestamp()
  }
}
