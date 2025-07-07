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
  cluster_wi_principal_prefix       = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  huggingface_hub_downloader_member = "${local.cluster_wi_principal_prefix}/ns/${local.huggingface_hub_downloader_kubernetes_namespace_name}/sa/${local.huggingface_hub_downloader_kubernetes_service_account_name}"
}

resource "google_storage_bucket_iam_member" "hub_models_downloader" {
  for_each = tomap({
    google_service_account     = data.google_service_account.hub_downloader.member
    kubernetes_service_account = local.huggingface_hub_downloader_member
  })

  bucket = data.google_storage_bucket.hub_models.name
  member = each.value
  role   = local.cluster_gcsfuse_user_role
}

resource "google_secret_manager_secret_iam_member" "hub_access_token_read_downloader" {
  for_each = tomap({
    google_service_account     = data.google_service_account.hub_downloader.member
    kubernetes_service_account = local.huggingface_hub_downloader_member
  })

  member    = each.value
  project   = data.google_secret_manager_secret.hub_access_token_read.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.hub_access_token_read.secret_id
}

resource "google_secret_manager_secret_iam_member" "hub_access_token_write_downloader" {
  for_each = tomap({
    google_service_account     = data.google_service_account.hub_downloader.member
    kubernetes_service_account = local.huggingface_hub_downloader_member
  })

  member    = each.value
  project   = data.google_secret_manager_secret.hub_access_token_write.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.hub_access_token_write.secret_id
}
