
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
  acp_root             = "${path.module}/../../../../../../.."
  repositories_path    = "platforms/cws/image_pipeline/repositories"
  repository_directory = "${local.repositories_path}/repository-${local.unique_identifier_prefix}"
  local_directory      = "platforms/cws/image_pipeline/terraform/images/comfyui/nvidia/repo_files"

  custom_nodes_directory = "${path.module}/../custom_nodes"
  custom_nodes_files     = fileset(local.custom_nodes_directory, "**")
  repository_folder      = "${path.module}/../../../../repository-${local.unique_identifier_prefix}"
}

resource "local_file" "cloudbuild_yaml" {
  content = templatefile(
    "${path.module}/templates/repository/cloudbuild/comfyui-nvidia.yaml",
    {
      cloudbuild_cws_image_registry_name = local.cloudbuild_cws_image_registry_name,
    }
  )
  file_permission = "0644"
  filename        = "${local.acp_root}/${local.local_directory}/cloudbuild/comfyui-nvidia.yaml"
}

resource "local_file" "custom_nodes" {
  for_each = local.custom_nodes_files

  content  = file("${local.custom_nodes_directory}/${each.value}")
  filename = "${local.acp_root}/${local.local_directory}/container-images/comfyui/custom_nodes/${each.value}"
}

resource "local_file" "dockerfile" {
  content = templatefile(
    "${path.module}/templates/repository/container-images/comfyui/nvidia/Dockerfile",
    {
      cloudbuild_cws_image_registry_upstream_name = local.cloudbuild_cws_image_registry_upstream_name,
    }
  )
  file_permission = "0644"
  filename        = "${local.acp_root}/${local.local_directory}/container-images/comfyui/nvidia/Dockerfile"
}

resource "local_file" "start_ide" {
  content         = file("${path.module}/templates/repository/container-images/comfyui/nvidia/etc/workstation-startup.d/110_start-comfyui.sh")
  file_permission = "0644"
  filename        = "${local.acp_root}/${local.local_directory}/container-images/comfyui/nvidia/etc/workstation-startup.d/110_start-comfyui.sh"
}

resource "terraform_data" "stage_files" {
  depends_on = [
    local_file.cloudbuild_yaml,
    local_file.custom_nodes,
    local_file.dockerfile,
    local_file.start_ide,
  ]

  input = {
    content_hash = sha512(
      join("",
        [
          "${local_file.cloudbuild_yaml.content_sha512}",
          "${local_file.dockerfile.content_sha512}",
          "${local_file.start_ide.content_sha512}",
        ]
      )
    )
    local_directory      = local.local_directory
    repository_directory = local.repository_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir --parents "${self.input.repository_directory}/"
cp \
--preserve=mode,ownership,timestamps \
--recursive \
"${self.input.local_directory}"/* \
"${self.input.repository_directory}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash = sha512(
      join("",
        [
          "${local_file.cloudbuild_yaml.content_sha512}",
          "${local_file.dockerfile.content_sha512}",
          "${local_file.start_ide.content_sha512}",
        ]
      )
    )
  }
}
