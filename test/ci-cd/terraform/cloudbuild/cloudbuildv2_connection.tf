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

data "google_secret_manager_secret" "github_token" {
  project   = data.google_project.build.project_id
  secret_id = local.build_github_token_secret
}

data "google_secret_manager_secret_version" "github_token" {
  secret = data.google_secret_manager_secret.github_token.id
}

resource "google_secret_manager_secret_iam_member" "cloudbuild_secretmanager_secret_accessor" {
  project   = data.google_project.build.project_id
  secret_id = data.google_secret_manager_secret.github_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:service-${data.google_project.build.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

resource "google_cloudbuildv2_connection" "github" {
  depends_on = [
    google_secret_manager_secret_iam_member.cloudbuild_secretmanager_secret_accessor,
  ]

  location = var.build_location
  name     = "github"
  project  = data.google_project.build.project_id

  github_config {
    app_installation_id = 261964

    authorizer_credential {
      oauth_token_secret_version = "${data.google_secret_manager_secret.github_token.id}/versions/latest"
    }
  }
}

resource "google_cloudbuildv2_repository" "accelerated_platforms" {
  location          = var.build_location
  name              = "GoogleCloudPlatform-accelerated-platforms"
  parent_connection = google_cloudbuildv2_connection.github.name
  project           = data.google_project.build.project_id
  remote_uri        = "https://github.com/GoogleCloudPlatform/accelerated-platforms.git"
}
