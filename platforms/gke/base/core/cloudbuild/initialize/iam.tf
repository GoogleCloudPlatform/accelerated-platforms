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

resource "google_project_iam_member" "cloudbuild_builds_builder_cloudbuild" {
  member  = data.google_service_account.cloudbuild.member
  project = local.cloudbuild_project_id
  role    = "roles/cloudbuild.builds.builder"
}

resource "google_storage_bucket_iam_member" "source_cloudbuild" {
  bucket = data.google_storage_bucket.source.name
  member = data.google_service_account.cloudbuild.member
  role   = "roles/storage.admin"
}

resource "google_secret_manager_secret_iam_member" "github_access_token_read_cloudbuild" {
  member    = data.google_service_account.cloudbuild.member
  project   = data.google_secret_manager_secret.github_access_token_read.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.github_access_token_read.secret_id
}

resource "google_secret_manager_secret_iam_member" "github_access_token_write_cloudbuild" {
  member    = data.google_service_account.cloudbuild.member
  project   = data.google_secret_manager_secret.github_access_token_write.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.github_access_token_write.secret_id
}
