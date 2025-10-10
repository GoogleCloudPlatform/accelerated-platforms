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

data "google_secret_manager_secret" "git_token" {
  project   = data.google_project.image_pipeline_git_token.project_id
  secret_id = local.cloudbuild_cws_image_pipeline_git_token_secret_id
}

data "google_secret_manager_secret_version" "git_token_latest" {
  secret = data.google_secret_manager_secret.git_token.id
}
