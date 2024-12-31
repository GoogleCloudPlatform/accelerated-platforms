# Copyright 2024 Google LLC
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
  config_management_destination_directory_path = "${path.module}/files/config_management"
  push_container_image_script_path             = "${path.module}/scripts/build-push-container-image.sh"
}

resource "terraform_data" "config_management_oci_archive_push" {

  provisioner "local-exec" {
    command = local.push_container_image_script_path

    environment = {
      CONTAINER_IMAGE_BUILD_CONTEXT_PATH = local.config_management_destination_directory_path
      CONTAINER_IMAGE_REPOSITORY_DOMAIN  = local.oci_repo_domain
      CONTAINER_IMAGE_REPOSITORY_URL     = local.oci_repo_url
      CONTAINER_IMAGE_DESTINATION_TAG    = local.oci_sync_repo_url
    }
  }

  triggers_replace = [
    # Trigger whenever the contents of the config_management directory change
    sha512(join("", [for f in fileset(local.config_management_destination_directory_path, "**") : filesha512("${local.config_management_destination_directory_path}/${f}")])),
    # Trigger whenever the contents of the container image push script change
    filesha512(local.push_container_image_script_path),
    local.config_management_destination_directory_path,
    local.oci_repo_domain,
    local.oci_repo_url,
    local.oci_sync_repo_url,
  ]
}
