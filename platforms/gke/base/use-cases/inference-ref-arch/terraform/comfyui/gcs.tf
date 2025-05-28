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

resource "google_storage_bucket" "comfyui_input" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_input_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "comfyui_model" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_model_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "comfyui_output" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_output_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "cloudbuild_source" {
  location                    = local.comfyui_cloudbuild_source_bucket_location
  force_destroy               = true
  name                        = local.comfyui_cloudbuild_source_bucket_name
  project                     = local.comfyui_cloudbuild_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}
