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
  final_artifact_repo_name = split("/", google_artifact_registry_repository.comfyui_container_images.id)[5]
  image_destination        = "${var.cluster_region}-docker.pkg.dev/${data.google_project.default.project_id}/${local.final_artifact_repo_name}/${var.comfyui_image_name}:${var.comfyui_image_tag}"
}

resource "null_resource" "submit_docker_build" {
  triggers = {
    repository_id     = google_artifact_registry_repository.comfyui_container_images.id
    custom_sa_email   = google_service_account.custom_cloudbuild_sa.email
    image_tag         = var.comfyui_image_tag
    build_config_hash = filebase64sha256("${path.module}/src/cloudbuild.yaml")
    dockerfile_hash   = filebase64sha256("${path.module}/src/Dockerfile")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd src && gcloud builds submit \
             --config="${path.module}/cloudbuild.yaml" \
             --service-account="projects/${data.google_project.default.project_id}/serviceAccounts/${google_service_account.custom_cloudbuild_sa.email}" \
             --gcs-source-staging-dir="${google_storage_bucket.docker_staging_bucket.url}/source" \
             --project="${data.google_project.default.project_id}" \
             --substitutions=_DESTINATION="${local.image_destination}"
    EOT

    when = create
  }
  depends_on = [
    google_project_iam_member.custom_cloudbuild_sa_log_writer
  ]
}
