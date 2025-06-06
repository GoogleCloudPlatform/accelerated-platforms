
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

resource "google_secret_manager_secret" "github_token" {
  project   = google_project_service.build_secretmanager_googleapis_com.project
  secret_id = local.build_github_token_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "huggingface_token_read" {
  project   = google_project_service.build_secretmanager_googleapis_com.project
  secret_id = local.build_huggingface_token_read_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "huggingface_token_write" {
  project   = google_project_service.build_secretmanager_googleapis_com.project
  secret_id = local.build_huggingface_token_write_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "ngc_api_key" {
  project   = google_project_service.build_secretmanager_googleapis_com.project
  secret_id = local.build_ngc_api_key_secret

  replication {
    auto {}
  }
}
