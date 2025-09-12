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

resource "google_storage_bucket" "source" {
  force_destroy               = true
  location                    = local.cloudbuild_location
  name                        = local.cloudbuild_source_bucket_name
  project                     = local.cloudbuild_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }
}

data "google_storage_bucket" "source" {
  depends_on = [
    google_storage_bucket.source,
  ]

  name    = local.cloudbuild_source_bucket_name
  project = local.cloudbuild_project_id
}

resource "google_storage_bucket_iam_member" "cloudbuild_source_storage_admin" {
  depends_on = [
    data.google_service_account.cloudbuild
  ]

  for_each = toset([
    local.cloudbuild_service_account_member,
  ])

  bucket = data.google_storage_bucket.source.name
  member = each.key
  role   = "roles/storage.admin"
}
