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
  gsa_build_roles = [
    "roles/logging.logWriter",
  ]
  wi_member_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject/ns/${var.fine_tuning_team_namespace}/sa"
}

resource "google_project_iam_member" "fine_tuning_build" {
  for_each = toset(local.gsa_build_roles)

  project = google_service_account.fine_tuning_build.project
  member  = google_service_account.fine_tuning_build.member
  role    = each.value
}

resource "google_artifact_registry_repository_iam_member" "container_images_gsa_build_artifactregistry_writer" {
  location   = google_artifact_registry_repository.fine_tuning.location
  member     = google_service_account.fine_tuning_build.member
  project    = google_artifact_registry_repository.fine_tuning.project
  repository = google_artifact_registry_repository.fine_tuning.name
  role       = "roles/artifactregistry.writer"
}

resource "google_storage_bucket_iam_member" "cloudbuild_bucket_gsa_build_storage_object_viewer" {
  bucket = google_storage_bucket.cloudbuild.name
  member = google_service_account.fine_tuning_build.member
  role   = "roles/storage.objectViewer"
}

# AIPLATFORM
###########################################################
resource "google_project_iam_member" "data_preparation_aiplatform_user" {
  project = google_project_service.aiplatform_googleapis_com.project
  member  = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["data-preparation"].service_account_name}"
  role    = "roles/aiplatform.user"
}

# DATA BUCKET
###########################################################
resource "google_storage_bucket_iam_member" "data_bucket_batch_inference_storage_object_user" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["batch-inference"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "data_bucket_batch_inference_storage_insights_collector_service" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["batch-inference"].service_account_name}"
  role   = "roles/storage.insightsCollectorService"
}

resource "google_storage_bucket_iam_member" "data_bucket_data_preparation_storage_object_user" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["data-preparation"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "data_bucket_data_processing_ksa_storage_object_user" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["data-processing"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "data_bucket_fine_tuning_storage_object_user" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["fine-tuning"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "data_bucket_model_evaluation_storage_insights_collector_service" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["model-evaluation"].service_account_name}"
  role   = "roles/storage.insightsCollectorService"
}

resource "google_storage_bucket_iam_member" "data_bucket_model_evaluation_storage_object_user" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["model-evaluation"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "data_bucket_ray_head_storage_object_viewer" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["ray-head"].service_account_name}"
  role   = "roles/storage.objectViewer"
}

resource "google_storage_bucket_iam_member" "data_bucket_ray_worker_storage_object_admin" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["ray-worker"].service_account_name}"
  role   = "roles/storage.objectAdmin"
}

# MODEL BUCKET
###########################################################
resource "google_storage_bucket_iam_member" "model_bucket_fine_tuning_storage_object_user" {
  bucket = google_storage_bucket.model.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["fine-tuning"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "model_bucket_model_evaluation_storage_object_user" {
  bucket = google_storage_bucket.model.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["model-evaluation"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "model_bucket_model_ops_storage_object_user" {
  bucket = google_storage_bucket.model.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["model-ops"].service_account_name}"
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "model_bucket_model_serve_storage_object_user" {
  bucket = google_storage_bucket.model.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["model-serve"].service_account_name}"
  role   = "roles/storage.objectUser"
}
