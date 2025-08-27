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
  acp_root            = "${path.module}/../../../.."
  temporary_directory = "${var.temporary_directory}/${var.namespace}/${var.repository}/${random_id.temporary_folder.hex}"
  lock_file           = "${var.temporary_directory}/${var.namespace}/${var.repository}/.lock"
}

resource "random_id" "temporary_folder" {
  byte_length = 8
}

#TODO: Enhance all triggers_replace

resource "terraform_data" "lock" {
  input = {
    lock_file           = local.lock_file
    lock_timeout        = var.lock_timeout
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
timeout ${self.input.lock_timeout} bash -c '
while [ -f "${self.input.lock_file}" ]; do
  echo "Waiting for lock_file: ${self.input.lock_file}..."
  sleep 1
done
'
mkdir --parents "${self.input.temporary_directory}"
touch "${self.input.lock_file}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash        = var.content_hash
    lock_file           = local.lock_file
    temporary_directory = local.temporary_directory
  }
}

resource "terraform_data" "git_clone" {
  depends_on = [
    terraform_data.lock
  ]

  input = {
    lock_file           = local.lock_file
    provider            = var.git_provider
    namespace           = var.namespace
    repository          = var.repository
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
git clone \
https://${self.input.provider}/${self.input.namespace}/${self.input.repository}.git \
${self.input.temporary_directory} 
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash        = var.content_hash
    lock_file           = local.lock_file
    provider            = var.git_provider
    namespace           = var.namespace
    repository          = var.repository
    temporary_directory = local.temporary_directory
  }
}

resource "terraform_data" "copy_files" {
  depends_on = [
    terraform_data.git_clone,
  ]

  input = {
    directory_to_commit = var.directory_to_commit
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
pwd
cp \
--preserve=mode,ownership,timestamps \
--recursive \
"${self.input.directory_to_commit}/"* \
"${self.input.temporary_directory}/"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash        = var.content_hash
    directory_to_commit = var.directory_to_commit
    temporary_directory = local.temporary_directory
  }
}

resource "terraform_data" "git_commit" {
  depends_on = [
    terraform_data.copy_files,
  ]

  input = {
    commit_message      = var.commit_message
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
if [[ -n "$(git -C ${self.input.temporary_directory} status --porcelain)" ]]; then
  echo "Changes or untracked files detected, committing changes."
  git -C ${self.input.temporary_directory} add .
  git -C ${self.input.temporary_directory} \
  commit \
  --message="${self.input.commit_message}"
else
  echo "No changes detected."
fi
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    commit_message      = var.commit_message
    content_hash        = var.content_hash
    temporary_directory = local.temporary_directory
  }
}

resource "terraform_data" "git_push" {
  depends_on = [
    terraform_data.git_commit,
  ]

  input = {
    lock_file           = local.lock_file
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
git -C ${self.input.temporary_directory} push
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash        = var.content_hash
    lock_file           = local.lock_file
    temporary_directory = local.temporary_directory
  }
}

resource "terraform_data" "cleanup" {
  depends_on = [
    terraform_data.git_push,
  ]

  input = {
    lock_file           = local.lock_file
    temporary_directory = local.temporary_directory
  }

  provisioner "local-exec" {
    command     = <<EOT
rm --force --recursive "${self.input.temporary_directory}"
rm --force "${self.input.lock_file}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    content_hash        = var.content_hash
    lock_file           = local.lock_file
    temporary_directory = local.temporary_directory
  }
}
