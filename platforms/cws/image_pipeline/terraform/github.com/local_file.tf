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
  acp_root             = "${path.module}/../../../../.."
  repositories_path    = "platforms/cws/image_pipeline/repositories"
  repository_directory = "${local.repositories_path}/${var.cloudbuild_cws_image_pipeline_git_namespace}/${local.cloudbuild_cws_image_pipeline_git_repository_name}/local"
}

resource "terraform_data" "local_git_repository" {
  # depends_on = [
  #   module.github_repository,
  # ]

  input = {
    acp_root             = local.acp_root
    repository_clone_url = local.cloudbuild_cws_image_pipeline_git_repository_clone_url
    repository_directory = local.repository_directory
  }

  # TODO: add credential support
  provisioner "local-exec" {
    command     = <<EOT
mkdir --parent ${self.input.repository_directory}
git clone ${self.input.repository_clone_url} ${self.input.repository_directory} 
EOT
    interpreter = ["bash", "-c"]
    working_dir = self.input.acp_root
  }

  provisioner "local-exec" {
    command     = <<EOT
rm --force --recursive ${self.input.repository_directory}
EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = self.input.acp_root
  }
}
