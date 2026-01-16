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
  cluster_wi_principal_prefix         = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  ira_inference_perf_bench_ksa_member = "${local.cluster_wi_principal_prefix}/ns/${local.ira_inference_perf_bench_kubernetes_namespace_name}/sa/${local.ira_inference_perf_bench_kubernetes_service_account_name}"
}

resource "google_storage_bucket_iam_member" "hub_models_ira_inference_perf_bench_ksa" {
  bucket = data.google_storage_bucket.bench_results.name
  member = local.ira_inference_perf_bench_ksa_member
  role   = "roles/storage.objectUser"
}

resource "google_project_iam_member" "hub_models_ira_inference_perf_bench_ksa_roles" {
  project  = var.platform_default_project_id
  member   = local.ira_inference_perf_bench_ksa_member
  for_each = toset(local.ira_inference_perf_ksa_project_roles_list)
  role     = each.value
}
