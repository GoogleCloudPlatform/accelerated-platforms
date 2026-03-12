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

resource "google_storage_bucket" "cloudbuild" {
  force_destroy               = true
  location                    = local.mft_region
  name                        = local.mft_bucket_cloudbuild_name
  project                     = data.google_project.cluster.project_id
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "data" {
  force_destroy               = true
  location                    = local.mft_region
  name                        = local.mft_data_bucket_name
  project                     = data.google_project.cluster.project_id
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "model" {
  force_destroy               = true
  location                    = local.mft_region
  name                        = local.mft_bucket_model_name
  project                     = data.google_project.cluster.project_id
  uniform_bucket_level_access = true
}
