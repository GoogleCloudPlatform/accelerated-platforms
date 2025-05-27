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

resource "google_storage_bucket_iam_member" "ira_cloud_storage_bucket_iam_member" {
  for_each = {
    for iam_binding in var.ira_cloud_storage_buckets_iam_bindings : "${iam_binding.bucket_name}-${iam_binding.member}-${iam_binding.role}" => iam_binding
  }

  bucket = google_storage_bucket.ira_cloud_storage_buckets[each.value.bucket_name].name
  role   = each.value.role
  member = "${local.workload_identity_principal_prefix}/ns/${each.value.member}"
}
