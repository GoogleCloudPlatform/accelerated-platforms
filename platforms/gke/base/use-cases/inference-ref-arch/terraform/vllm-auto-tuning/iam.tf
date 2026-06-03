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

resource "google_storage_bucket_iam_member" "auto_tuning_bucket_access_at_ksa" {
  bucket = google_storage_bucket.auto_tuning_results.name
  member = local.ira_auto_tuning_vllm_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "hub_models_bucket_access_at_ksa" {
  bucket = local.huggingface_hub_models_bucket_name
  member = local.ira_auto_tuning_vllm_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_secret_manager_secret_iam_member" "hub_token_read_access_at_ksa" {
  member    = local.ira_auto_tuning_vllm_ksa_member
  project   = data.google_secret_manager_secret.hub_access_token_read.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.hub_access_token_read.secret_id
}
