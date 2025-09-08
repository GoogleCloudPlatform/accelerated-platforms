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

resource "google_artifact_registry_repository" "repository" {
  for_each = toset(var.configmanagement_sync_repo == null ? ["managed"] : [])

  format        = "DOCKER"
  location      = local.cluster_region
  project       = google_project_service.artifactregistry_googleapis_com.project
  repository_id = local.oci_repo_id

  lifecycle {
    ignore_changes = [
      labels
    ]
  }
}

data "google_artifact_registry_repository" "repository" {
  depends_on = [
    google_artifact_registry_repository.repository,
  ]

  location      = local.cluster_region
  project       = google_project_service.artifactregistry_googleapis_com.project
  repository_id = local.oci_repo_id
}
