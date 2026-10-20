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

data "google_storage_bucket" "hub_models" {
  name    = local.huggingface_hub_models_bucket_name
  project = local.huggingface_hub_models_bucket_project_id
}

# Rapid Cache (formerly Anywhere Cache) is a zonal, SSD-backed read cache for
# the model bucket. The API and the Terraform resource still use the name
# Anywhere Cache. Destroying this resource disables the cache, and Cloud Storage
# deletes a disabled cache after a grace period of 1 hour. A bucket can't be
# deleted while it has caches.
resource "google_storage_anywhere_cache" "hub_models" {
  for_each = toset(var.ira_online_gpu_rapid_cache_zones)

  bucket          = data.google_storage_bucket.hub_models.name
  ingest_on_write = var.ira_online_gpu_rapid_cache_ingest_on_write
  ttl             = var.ira_online_gpu_rapid_cache_ttl
  zone            = each.value
}
