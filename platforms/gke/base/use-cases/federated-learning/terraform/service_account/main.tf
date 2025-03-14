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

locals {
  node_pool_service_accounts_iam_roles_setproduct = setproduct(local.cluster_sa_roles, local.node_pool_service_account_iam_emails)

  node_pool_service_accounts_iam_members = {
    for entry in local.node_pool_service_accounts_iam_roles_setproduct : "${entry[0]}-${entry[1]}" => entry
  }
}

resource "google_service_account" "federated_learning_service_account" {
  for_each = toset(local.service_account_names)

  account_id   = each.value
  description  = "Terraform-managed service account for the federated learning use case in cluster ${local.cluster_name}"
  display_name = "${local.cluster_name}-${each.value} service account"
  project      = google_project_service.iam_googleapis_com.project
}

resource "google_project_iam_member" "node_pool_service_account" {
  for_each = local.node_pool_service_accounts_iam_members

  member  = each.value[1]
  project = google_project_service.iam_googleapis_com.project
  role    = each.value[0]

  depends_on = [
    # Wait for service account creation before attempting to assign roles
    google_service_account.federated_learning_service_account
  ]
}
