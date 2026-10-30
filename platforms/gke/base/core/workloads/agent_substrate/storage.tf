# Copyright 2026 Google LLC
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
  agent_substrate_snapshot_bucket_name = var.agent_substrate_snapshot_bucket_name != null ? var.agent_substrate_snapshot_bucket_name : "${local.unique_identifier_prefix}-ate-snapshots-${local.cluster_project_id}"
  agent_substrate_assets_bucket_name   = "${local.agent_substrate_snapshot_bucket_name}-assets"
}

resource "google_storage_bucket" "snapshot" {
  name                        = local.agent_substrate_snapshot_bucket_name
  project                     = data.google_project.cluster.project_id
  location                    = local.cluster_region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

resource "google_storage_bucket" "assets" {
  name                        = local.agent_substrate_assets_bucket_name
  project                     = data.google_project.cluster.project_id
  location                    = local.cluster_region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
}
