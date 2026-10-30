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
  cluster_wi_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  atelet_wi_member            = "${local.cluster_wi_principal_prefix}/ns/ate-system/sa/atelet"
  ate_api_server_wi_member    = "${local.cluster_wi_principal_prefix}/ns/ate-system/sa/ate-api-server"
}

resource "google_project_iam_member" "atelet_artifactregistry_reader" {
  member  = local.atelet_wi_member
  project = data.google_project.cluster.project_id
  role    = "roles/artifactregistry.reader"
}

resource "google_service_account_iam_member" "ate_api_server_token_creator" {
  member             = local.ate_api_server_wi_member
  role               = "roles/iam.serviceAccountTokenCreator"
  service_account_id = google_service_account.snapshot_transfer.name
}

resource "google_storage_bucket_iam_member" "snapshot_object_admin" {
  for_each = tomap({
    ate_api_server    = local.ate_api_server_wi_member
    snapshot_transfer = google_service_account.snapshot_transfer.member
  })

  bucket = google_storage_bucket.snapshot.name
  member = each.value
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "snapshot_bucket_viewer" {
  for_each = tomap({
    ate_api_server    = local.ate_api_server_wi_member
    snapshot_transfer = google_service_account.snapshot_transfer.member
  })

  bucket = google_storage_bucket.snapshot.name
  member = each.value
  role   = "roles/storage.bucketViewer"
}

resource "google_storage_bucket_iam_member" "assets_atelet_viewer" {
  bucket = google_storage_bucket.assets.name
  member = local.atelet_wi_member
  role   = "roles/storage.objectViewer"
}
