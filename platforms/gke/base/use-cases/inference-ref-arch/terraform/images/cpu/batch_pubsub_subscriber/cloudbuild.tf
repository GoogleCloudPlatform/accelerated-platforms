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
  image_destination = local.ira_online_cpu_batch_pubsub_subscriber_image_url
}

resource "terraform_data" "submit_docker_build" {
  input = {
    acp_root                      = local.acp_root
    cloudbuild_project_id         = local.cloudbuild_project_id
    cloudbuild_service_account_id = local.cloudbuild_service_account_id
    cloudbuild_source_bucket_name = local.cloudbuild_source_bucket_name
    image_destination             = local.image_destination
  }

  provisioner "local-exec" {
    command     = <<-EOT
gcloud builds submit \
--config="container-images/cpu/batch-pubsub-subscriber/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${self.input.cloudbuild_source_bucket_name}/source" \
--project="${self.input.cloudbuild_project_id}" \
--quiet \
--service-account="${self.input.cloudbuild_service_account_id}" \
--substitutions=_DESTINATION="${self.input.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = self.input.acp_root
  }

  triggers_replace = {
    cloudbuild_yaml_hash = filebase64sha256("${local.acp_root}/container-images/cpu/batch-pubsub-subscriber/cloudbuild.yaml")
    dockerfile_hash      = filebase64sha256("${local.acp_root}/container-images/cpu/batch-pubsub-subscriber/Dockerfile")
    source_hash          = sha256(join("", [for file in fileset("${local.acp_root}/container-images/cpu/batch-pubsub-subscriber/src", "**") : filesha256("${local.acp_root}/container-images/cpu/batch-pubsub-subscriber/src/${file}")]))
  }
}
