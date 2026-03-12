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
  image_destination = local.mft_data_preparation_image_url
  image_directory   = "container-images/cpu/mft-data-preparation/gemma-it/"
  source_folder     = "${local.acp_root}/container-images/cpu/mft-data-preparation/gemma-it/src"
}

resource "terraform_data" "submit_docker_build" {
  input = {
    acp_root                      = local.acp_root
    cloudbuild_project_id         = local.cloudbuild_project_id
    cloudbuild_service_account_id = local.cloudbuild_service_account_id
    cloudbuild_source_bucket_name = local.cloudbuild_source_bucket_name
    image_destination             = local.image_destination
    image_directory               = local.image_directory
  }

  provisioner "local-exec" {
    command     = <<-EOT
gcloud beta builds submit \
--config="${self.input.image_directory}/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${self.input.cloudbuild_source_bucket_name}/source" \
--ignore-file=${self.input.image_directory}/.gcloudignore \
--project="${self.input.cloudbuild_project_id}" \
--quiet \
--service-account="${self.input.cloudbuild_service_account_id}" \
--substitutions=_DESTINATION="${self.input.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = self.input.acp_root
  }

  triggers_replace = {
    always_run           = timestamp()
    cloudbuild_yaml_hash = filebase64sha256("${local.acp_root}/${local.image_directory}/cloudbuild.yaml")
    dockerfile_hash      = filebase64sha256("${local.acp_root}/${local.image_directory}/Dockerfile")
    ignore_file_hash     = filebase64sha256("${local.acp_root}/${local.image_directory}/.gcloudignore")
    source_hash          = sha256(join("", [for file in fileset("${local.source_folder}", "**") : filesha256("${local.source_folder}/${file}")]))
  }
}
