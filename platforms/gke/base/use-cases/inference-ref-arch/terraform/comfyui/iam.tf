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
  workload_identity_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_artifactregistry_write" {
  location   = local.cluster_region
  member     = data.google_service_account.cloudbuild.member
  project    = data.google_project.cluster.project_id
  repository = google_artifact_registry_repository.comfyui_container_images.repository_id
  role       = "roles/artifactregistry.writer"
}

resource "google_storage_bucket_iam_member" "cloudbuild_gcsfuse_user" {
  bucket = google_storage_bucket.comfyui_model.name
  member = data.google_service_account.cloudbuild.member
  role   = local.cluster_gcsfuse_user_role
}

resource "google_project_iam_member" "workload_identity_vertex_ai_user_binding" {
  member  = "${local.workload_identity_principal_prefix}/ns/${var.comfyui_kubernetes_namespace}/sa/${local.serviceaccount}"
  project = data.google_project.cluster.project_id
  role    = "roles/aiplatform.user"
}

resource "google_storage_bucket_iam_member" "workload_identity_gcsfuse_user" {
  for_each = toset([
    google_storage_bucket.comfyui_input.name,
    google_storage_bucket.comfyui_model.name,
    google_storage_bucket.comfyui_output.name,
    google_storage_bucket.comfyui_workflow.name,
  ])

  bucket = each.key
  member = "${local.workload_identity_principal_prefix}/ns/${var.comfyui_kubernetes_namespace}/sa/${local.serviceaccount}"
  role   = local.cluster_gcsfuse_user_role
}

resource "google_storage_bucket_iam_member" "ai_service_agent_gcs_role" {
  depends_on = [
    google_project_service_identity.aiplatform_service_agents,
    google_project_service.cluster["aiplatform.googleapis.com"],
  ]

  for_each = toset([
    google_storage_bucket.comfyui_input.name,
    google_storage_bucket.comfyui_output.name,
  ])

  bucket = each.key
  member = "serviceAccount:${google_project_service_identity.aiplatform_service_agents.email}"
  role   = "roles/storage.objectUser"
}

