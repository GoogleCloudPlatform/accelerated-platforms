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
  image_destination = "${google_artifact_registry_repository.workflow_api_container_images.location}-docker.pkg.dev/${local.cluster_project_id}/${local.workflow_api_artifact_repo_name}/${var.workflow_api_image_name}:${var.workflow_api_image_tag}"
}

resource "terraform_data" "submit_docker_build" {
  provisioner "local-exec" {
    command     = <<-EOT
gcloud builds submit \
--config="cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${local.comfyui_cloudbuild_source_bucket_name}/source" \
--project="${data.google_project.cluster.project_id}" \
--quiet \
--service-account="projects/${data.google_project.cluster.project_id}/serviceAccounts/${local.comfyui_cloudbuild_service_account_email}" \
--substitutions=_DESTINATION="${local.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = "${path.module}/../../../../../../../projects/workflow-api"
  }

  triggers_replace = {
    custom_sa_email        = local.comfyui_cloudbuild_service_account_email
    hash_cloudbuild_config = filebase64sha256("${path.module}/../../../../../../../projects/workflow-api/cloudbuild.yaml")
    hash_dockerfile        = filebase64sha256("${path.module}/../../../../../../../projects/workflow-api/Dockerfile")
    image_tag              = var.workflow_api_image_tag
    repository_id          = google_artifact_registry_repository.workflow_api_container_images.id
  }
}
