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

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "google_project" "huggingface_hub_downloader_service_account" {
  project_id = local.huggingface_hub_downloader_service_account_project_id
}

data "google_project" "huggingface_secret_manager" {
  project_id = local.huggingface_secret_manager_project_id
}
