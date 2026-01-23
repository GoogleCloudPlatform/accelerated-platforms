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
  cluster_wi_principal_prefix                    = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  ira_inference_perf_bench_online_gpu_ksa_member = "${local.cluster_wi_principal_prefix}/ns/${local.ira_online_gpu_kubernetes_namespace_name}/sa/${local.ira_inference_perf_bench_kubernetes_service_account_name}"
  ira_inference_perf_bench_online_tpu_ksa_member = "${local.cluster_wi_principal_prefix}/ns/${local.ira_online_tpu_kubernetes_namespace_name}/sa/${local.ira_inference_perf_bench_kubernetes_service_account_name}"

}

# --- GPU RESOURCES ---

resource "google_storage_bucket_iam_member" "hub_models_ira_inference_perf_bench_results_gpu_ksa" {
  count  = var.enable_gpu ? 1 : 0
  bucket = google_storage_bucket.bench_results.name
  member = local.ira_inference_perf_bench_online_gpu_ksa_member
  role   = "roles/storage.objectUser" 
}

resource "google_storage_bucket_iam_member" "hub_models_ira_inference_perf_bench_dataset_gpu_ksa" {
  count  = var.enable_gpu ? 1 : 0
  bucket = google_storage_bucket.bench_dataset.name
  member = local.ira_inference_perf_bench_online_gpu_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_project_iam_member" "hub_models_ira_inference_perf_bench_online_gpu_ksa_roles" {
  for_each = var.enable_gpu ? toset(local.ira_inference_perf_ksa_project_roles_list) : []
  project  = var.platform_default_project_id
  member   = local.ira_inference_perf_bench_online_gpu_ksa_member
  role     = each.value
}

resource "google_secret_manager_secret_iam_member" "hub_ira_inference_perf_bench_access_token_gpu_ksa_read" {
  count     = var.enable_gpu ? 1 : 0
  member    = local.ira_inference_perf_bench_online_gpu_ksa_member
  project   = data.google_secret_manager_secret.hub_access_token_read.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.hub_access_token_read.secret_id
}

# --- TPU RESOURCES ---

resource "google_storage_bucket_iam_member" "hub_models_ira_inference_perf_bench_results_tpu_ksa" {
  count  = var.enable_tpu ? 1 : 0
  bucket = google_storage_bucket.bench_results.name
  member = local.ira_inference_perf_bench_online_tpu_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "hub_models_ira_inference_perf_bench_dataset_tpu_ksa" {
  count  = var.enable_tpu ? 1 : 0
  bucket = google_storage_bucket.bench_dataset.name
  member = local.ira_inference_perf_bench_online_tpu_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_project_iam_member" "hub_models_ira_inference_perf_bench_online_tpu_ksa_roles" {
  for_each = var.enable_tpu ? toset(local.ira_inference_perf_ksa_project_roles_list) : []
  project  = var.platform_default_project_id
  member   = local.ira_inference_perf_bench_online_tpu_ksa_member
  role     = each.value
}

resource "google_secret_manager_secret_iam_member" "hub_ira_inference_perf_bench_access_token_tpu_ksa_read" {
  count     = var.enable_tpu ? 1 : 0
  member    = local.ira_inference_perf_bench_online_tpu_ksa_member
  project   = data.google_secret_manager_secret.hub_access_token_read.project
  role      = "roles/secretmanager.secretAccessor"
  secret_id = data.google_secret_manager_secret.hub_access_token_read.secret_id
}


