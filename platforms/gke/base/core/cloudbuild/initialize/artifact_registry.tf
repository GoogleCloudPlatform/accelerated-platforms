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

resource "google_artifact_registry_repository" "cloudbuild" {
  for_each = toset(var.cloudbuild_ar_image_repository_name == null ? ["managed"] : [])

  description   = "Cloud Build image repository for ${local.unique_identifier_prefix}"
  format        = "DOCKER"
  location      = local.cloudbuild_ar_location
  project       = google_project_service.artifact_registry["artifactregistry.googleapis.com"].project
  repository_id = local.cloudbuild_ar_image_repository_name
}

data "google_artifact_registry_repository" "cloudbuild" {
  depends_on = [
    google_artifact_registry_repository.cloudbuild
  ]

  location      = local.cloudbuild_ar_location
  project       = google_project_service.artifact_registry["artifactregistry.googleapis.com"].project
  repository_id = local.cloudbuild_ar_image_repository_name
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_artifactregistry_writer" {
  depends_on = [
    data.google_artifact_registry_repository.cloudbuild,
    data.google_service_account.cloudbuild,
  ]

  for_each = toset([
    local.cloudbuild_service_account_member,
  ])

  location   = data.google_artifact_registry_repository.cloudbuild.location
  member     = each.key
  project    = data.google_artifact_registry_repository.cloudbuild.project
  repository = data.google_artifact_registry_repository.cloudbuild.repository_id
  role       = "roles/artifactregistry.writer"
}
