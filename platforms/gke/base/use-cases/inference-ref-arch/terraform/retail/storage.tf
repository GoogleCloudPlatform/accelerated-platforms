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

locals {
  dataflow_staging_bucket = "${local.unique_identifier_prefix}-dataflow-staging"
  batches_bucket          = "${local.unique_identifier_prefix}-batches"
}

resource "google_storage_bucket" "batches_bucket" {
  name                        = local.batches_bucket
  location                    = local.cluster_region
  project                     = data.google_project.cluster.project_id
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 7
    }
  }
}

resource "google_storage_bucket" "dataflow_staging_bucket" {
  name                        = local.dataflow_staging_bucket
  location                    = local.cluster_region
  project                     = data.google_project.cluster.project_id
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }
}
