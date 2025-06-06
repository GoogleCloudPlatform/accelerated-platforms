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

resource "google_storage_bucket" "nvidia_nim_model_store" {
  force_destroy               = false
  location                    = local.nvidia_nim_model_store_bucket_location
  name                        = local.nvidia_nim_model_store_bucket_name
  project                     = local.nvidia_nim_model_store_bucket_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }
}

data "google_storage_bucket" "nvidia_nim_model_store" {
  depends_on = [google_storage_bucket.nvidia_nim_model_store]

  name    = local.nvidia_nim_model_store_bucket_name
  project = local.nvidia_nim_model_store_bucket_project_id
}
