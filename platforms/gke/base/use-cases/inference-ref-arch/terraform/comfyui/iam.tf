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
  workload_identity_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.default.number}/locations/global/workloadIdentityPools/${data.google_project.default.project_id}.svc.id.goog/subject"
}

resource "google_storage_bucket_iam_member" "comfyui_storage_bucket_iam_member" {
  for_each = var.comfyui_storage_buckets
  bucket   = google_storage_bucket.comfyui_storage_buckets[each.key].name
  role     = "roles/storage.objectUser"
  member   = "${local.workload_identity_principal_prefix}/ns/${var.comfyui_kubernetes_namespace}/sa/${local.serviceaccount}"
}

resource "google_artifact_registry_repository_iam_member" "writer_access" {
  repository = google_artifact_registry_repository.comfyui_container_images.repository_id
  location   = var.cluster_region
  project    = data.google_project.default.project_id
  role       = "roles/artifactregistry.writer"
  member     = "${local.workload_identity_principal_prefix}/ns/${var.comfyui_kubernetes_namespace}/sa/${local.serviceaccount}"
}

# Create Custom Cloud Build SA and grant it permissions

resource "google_service_account" "custom_cloudbuild_sa" {
  account_id   = "${var.platform_name}-comfyui-build-sa"
  display_name = "Custom Service Account for Cloud Build"
  project      = data.google_project.default.project_id
}

resource "google_project_iam_member" "custom_cloudbuild_sa_artifact_writer" {
  project = data.google_project.default.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.custom_cloudbuild_sa.email}"
}

resource "google_project_iam_member" "custom_cloudbuild_sa_log_writer" {
  project = data.google_project.default.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.custom_cloudbuild_sa.email}"
}

resource "google_storage_bucket_iam_member" "docker_staging_bucket_creator" {
  bucket = google_storage_bucket.docker_staging_bucket.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.custom_cloudbuild_sa.email}"
}

resource "google_storage_bucket_iam_member" "model_bucket" {
  bucket = google_storage_bucket.comfyui_storage_buckets["comfyui-models"].name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.custom_cloudbuild_sa.email}"
}