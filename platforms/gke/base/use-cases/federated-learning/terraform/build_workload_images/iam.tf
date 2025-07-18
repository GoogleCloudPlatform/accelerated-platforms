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
  cloudbuild_sa_roles = [
    "roles/cloudbuild.builds.builder",
    "roles/cloudbuild.workerPoolUser",
    "roles/storage.objectUser",
    "roles/logging.logWriter"
  ]
}

data "google_service_account" "cloudbuild_sa" {
  account_id = local.cloudbuild_service_account_id
  project    = local.cloudbuild_project_id
}

resource "google_project_iam_member" "cloudbuild_sa_roles" {
  for_each = toset(local.cloudbuild_sa_roles)
  project  = data.google_project.cluster.name
  role     = each.key
  member   = data.google_service_account.cloudbuild_sa.member
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_artifact_registry_writer" {
  project    = data.google_project.cluster.name
  location   = local.cloudbuild_location
  repository = local.federated_learning_repository_id
  role       = "roles/artifactregistry.writer"
  member     = data.google_service_account.cloudbuild_sa.member
}
