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
  image_destination        = "${var.cluster_region}-docker.pkg.dev/${data.google_project.cluster.project_id}/${local.final_artifact_repo_name}/${var.comfyui_image_name}:${var.comfyui_image_tag}"
}

resource "terraform_data" "submit_docker_build" {
  depends_on = [
    google_project_iam_member.custom_cloudbuild_sa_log_writer,
    google_project_service.cloudbuild_googleapis_com,
    google_storage_bucket_iam_member.cloudbuild_source_creator,
  ]

  provisioner "local-exec" {
    command     = <<-EOT
      cd src && \
      while ! gcloud builds submit \
      --config="cloudbuild.yaml" \
      --gcs-source-staging-dir="${google_storage_bucket.cloudbuild_source.url}/source" \
      --project="${data.google_project.cluster.project_id}" \
      --quiet \
      --service-account="projects/${data.google_project.cluster.project_id}/serviceAccounts/${google_service_account.custom_cloudbuild_sa.email}" \
      --substitutions=_DESTINATION="${local.image_destination}"
      do
        sleep 5
      done
    EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    custom_sa_email        = google_service_account.custom_cloudbuild_sa.email
    hash_cloudbuild_config = filebase64sha256("${path.module}/src/cloudbuild.yaml")
    hash_dockerfile        = filebase64sha256("${path.module}/src/Dockerfile")
    hash_entrypoint        = filebase64sha256("${path.module}/src/entrypoint.sh")
    image_tag              = var.comfyui_image_tag
    repository_id          = google_artifact_registry_repository.comfyui_container_images.id
  }
}
