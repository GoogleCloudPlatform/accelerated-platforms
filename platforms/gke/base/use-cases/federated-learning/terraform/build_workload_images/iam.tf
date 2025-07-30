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

data "google_service_account" "cloudbuild_sa" {
  account_id = local.cloudbuild_service_account_id
  project    = local.cloudbuild_project_id
}

data "google_artifact_registry_repository" "artifact_registry" {
  project       = local.cloudbuild_project_id
  repository_id = local.federated_learning_repository_id
  location      = local.cloudbuild_location
}

resource "google_project_iam_member" "cloudbuild_sa_worker_pool_role" {
  project = local.cloudbuild_project_id
  role    = "roles/cloudbuild.workerPoolUser"
  member  = data.google_service_account.cloudbuild_sa.member
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_artifact_registry_writer" {
  project    = data.google_artifact_registry_repository.artifact_registry.project
  location   = data.google_artifact_registry_repository.artifact_registry.location
  repository = data.google_artifact_registry_repository.artifact_registry.repository_id
  role       = "roles/artifactregistry.writer"
  member     = data.google_service_account.cloudbuild_sa.member
}
