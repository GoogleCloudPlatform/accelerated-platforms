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
  wi_member_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject/ns/${local.sft_tpu_maxtext_multi_host_kubernetes_namespace_name}/sa/${local.sft_tpu_maxtext_multi_host_kubernetes_service_account_name}"
}

resource "google_storage_bucket" "sft_dataset" {
  name     = local.sft_tpu_maxtext_multi_host_dataset_bucket_name
  project  = local.sft_tpu_maxtext_multi_host_project_id
  location = local.cluster_region

  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_storage_bucket_iam_member" "sft_dataset_storage_object_admin" {
  bucket = google_storage_bucket.sft_dataset.name
  member = local.wi_member_principal_prefix
  role   = "roles/storage.objectAdmin"
}
