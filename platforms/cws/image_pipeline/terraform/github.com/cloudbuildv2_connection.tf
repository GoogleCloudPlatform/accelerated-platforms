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

resource "google_cloudbuildv2_connection" "gc_cloud_workstation_image" {
  # depends_on = [
  #   module.github_repository,
  # ]

  location = local.cloudbuild_location
  name     = local.cloudbuild_cws_image_pipeline_connection_name
  project  = data.google_project.cloudbuild.project_id

  github_config {
    app_installation_id = var.cloudbuild_cws_image_pipeline_gh_app_installation_id
    authorizer_credential {
      oauth_token_secret_version = "${data.google_secret_manager_secret.git_token.id}/versions/latest"
    }
  }
}

resource "google_cloudbuildv2_repository" "gc_cloud_workstation_image" {
  # depends_on = [
  #   module.github_repository,
  # ]

  location          = local.cloudbuild_location
  name              = local.cloudbuild_cws_image_pipeline_connection_name
  parent_connection = google_cloudbuildv2_connection.gc_cloud_workstation_image.name
  project           = data.google_project.cloudbuild.project_id
  remote_uri        = local.cloudbuild_cws_image_pipeline_git_repository_clone_url
}
