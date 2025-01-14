# Copyright 2024 Google LLC
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

resource "google_service_account_iam_member" "fl_workload_identity_service_account_iam_member" {
  for_each = local.tenants

  service_account_id = data.google_service_account.cluster_service_account[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = each.value.tenant_apps_workload_identity_service_account_name
}

data "google_service_account" "cluster_service_account" {
  for_each = local.tenants

  account_id = each.value.tenant_apps_sa_name
  project    = google_project_service.iam_googleapis_com.project
}
