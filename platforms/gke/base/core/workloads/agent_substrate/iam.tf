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

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

locals {
  ate_api_server_wi_member = "serviceAccount:${data.google_project.cluster.project_id}.svc.id.goog[${var.ate_kubernetes_namespace}/ate-api-server]"
  atelet_wi_principal      = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject/ns/${var.ate_kubernetes_namespace}/sa/atelet"
}

resource "google_service_account" "ate_api_server" {
  count = var.ate_service_account_name == null ? 1 : 0

  account_id   = local.ate_service_account_name
  display_name = "Agent Substrate API Server Service Account"
  project      = local.ate_service_account_project_id
}

data "google_service_account" "ate_api_server" {
  depends_on = [
    google_service_account.ate_api_server,
  ]

  account_id = local.ate_service_account_name
  project    = local.ate_service_account_project_id
}

resource "google_service_account_iam_member" "ate_api_server_workload_identity" {
  member             = local.ate_api_server_wi_member
  role               = "roles/iam.workloadIdentityUser"
  service_account_id = data.google_service_account.ate_api_server.name
}

resource "google_service_account_iam_member" "ate_api_server_token_creator" {
  member             = data.google_service_account.ate_api_server.member
  role               = "roles/iam.serviceAccountTokenCreator"
  service_account_id = data.google_service_account.ate_api_server.name
}

resource "google_project_iam_member" "ate_api_server_cloudsql_client" {
  member  = data.google_service_account.ate_api_server.member
  project = local.ate_cloudsql_project_id
  role    = "roles/cloudsql.client"
}

resource "google_project_iam_member" "ate_api_server_cloudsql_instance_user" {
  member  = data.google_service_account.ate_api_server.member
  project = local.ate_cloudsql_project_id
  role    = "roles/cloudsql.instanceUser"
}

resource "google_storage_bucket_iam_member" "ate_api_server_object_admin" {
  bucket = data.google_storage_bucket.ate.name
  member = data.google_service_account.ate_api_server.member
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "ate_api_server_bucket_viewer" {
  bucket = data.google_storage_bucket.ate.name
  member = data.google_service_account.ate_api_server.member
  role   = "roles/storage.bucketViewer"
}

resource "google_project_iam_member" "atelet_artifact_registry_reader" {
  member  = local.atelet_wi_principal
  project = local.cluster_project_id
  role    = "roles/artifactregistry.reader"
}

resource "google_storage_bucket_iam_member" "atelet_object_admin" {
  bucket = data.google_storage_bucket.ate.name
  member = local.atelet_wi_principal
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "atelet_bucket_viewer" {
  bucket = data.google_storage_bucket.ate.name
  member = local.atelet_wi_principal
  role   = "roles/storage.bucketViewer"
}
