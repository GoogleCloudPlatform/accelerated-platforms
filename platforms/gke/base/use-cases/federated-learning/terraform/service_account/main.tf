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

resource "google_service_account" "federated_learning_service_account" {
  for_each = toset(local.service_account_names)

  account_id   = lower(each.value)
  description  = "Terraform-managed service account for the federated learning use case in cluster ${local.cluster_name}"
  display_name = "${local.cluster_name}-${each.value} service account"
  project      = google_project_service.iam_googleapis_com.project
}
