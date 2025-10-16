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

# When implemented, only google_secret_manager_secret was supported for
# google_cloudbuildv2_connection.github_config.oauth_token_secret_version
# and not google_secret_manager_regional_secret.
resource "google_secret_manager_secret" "git_token" {
  for_each = toset(var.cloudbuild_cws_image_pipeline_git_token_secret_id == null ? ["managed"] : [])

  project   = google_project_service.image_pipeline_git_token["secretmanager.googleapis.com"].project
  secret_id = local.cloudbuild_cws_image_pipeline_git_token_secret_id

  replication {
    auto {}
  }
}

data "google_secret_manager_secret" "git_token" {
  depends_on = [
    google_secret_manager_secret.git_token
  ]

  project   = data.google_project.image_pipeline_git_token.project_id
  secret_id = local.cloudbuild_cws_image_pipeline_git_token_secret_id
}

resource "google_secret_manager_secret_version" "git_token_latest" {
  for_each = toset(var.cloudbuild_cws_image_pipeline_git_token_secret_id == null ? ["managed"] : [])

  secret      = data.google_secret_manager_secret.git_token.id
  secret_data = file("${local.platform_shared_config_folder}/${local.cloudbuild_cws_image_pipeline_git_token_file}")

  lifecycle {
    ignore_changes = [
      secret_data
    ]
  }
}

data "google_secret_manager_secret_version" "git_token_latest" {
  depends_on = [
    google_secret_manager_secret_version.git_token_latest
  ]

  secret = data.google_secret_manager_secret.git_token.id
}

resource "google_secret_manager_secret_iam_member" "cloudbuild_secretmanager_secret_accessor" {
  depends_on = [
    terraform_data.wait_for_cloudbuild_service_identity,
  ]

  member    = "serviceAccount:service-${data.google_project.cloudbuild.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
  project   = data.google_project.image_pipeline_git_token.project_id
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.git_token.secret_id
}
