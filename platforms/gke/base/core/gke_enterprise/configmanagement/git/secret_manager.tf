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

resource "google_secret_manager_secret" "git_creds_new" {
  for_each = toset(var.configmanagement_git_credentials.secret_name == null ? ["create"] : [])

  project   = google_project_service.secretmanager_googleapis_com.project
  secret_id = local.git_creds_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "git_creds_new" {
  for_each = toset(var.configmanagement_git_credentials.secret_name == null ? ["create"] : [])

  secret = google_secret_manager_secret.git_creds_new["create"].id

  secret_data = jsonencode({
    "token"    = var.configmanagement_git_credentials.token,
    "username" = var.configmanagement_git_credentials.username,
  })
}

data "google_secret_manager_secret" "git_creds" {
  depends_on = [google_secret_manager_secret_version.git_creds_new]

  project   = google_project_service.secretmanager_googleapis_com.project
  secret_id = local.git_creds_secret
}

data "google_secret_manager_secret_version" "git_creds" {
  secret = data.google_secret_manager_secret.git_creds.id
}
