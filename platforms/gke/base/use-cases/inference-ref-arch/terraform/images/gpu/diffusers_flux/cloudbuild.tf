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
  image_destination        = local.ira_online_gpu_diffusers_flux_image_url
}

resource "terraform_data" "submit_docker_build" {
  provisioner "local-exec" {
    command     = <<-EOT
gcloud builds submit \
--config="projects/diffusers-flux/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${local.cloudbuild_source_bucket_name}/source" \
--project="${local.cloudbuild_project_id}" \
--quiet \
--service-account="${local.cloudbuild_service_account_id}" \
--substitutions=_DESTINATION="${local.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    source                 = sha256(join("", [for file in fileset("${local.acp_root}/projects/diffusers-flux/src", "**") : filesha256("${local.acp_root}/projects/diffusers-flux/src/${file}")]))
    hash_cloudbuild_config = filebase64sha256("${local.acp_root}/projects/diffusers-flux/cloudbuild.yaml")
    hash_dockerfile        = filebase64sha256("${local.acp_root}/projects/diffusers-flux/Dockerfile")
  }
}
