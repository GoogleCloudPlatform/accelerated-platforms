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
  federated_learning_cross_device_example_wi_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"

  federated_learning_cross_device_example_workload_kubernetes_service_accounts = [
    for tenant in local.tenants : tenant.tenant_apps_workload_identity_service_account_name
  ]

  federated_learning_cross_device_example_workloads_iam_roles_setproduct = setproduct(concat(local.federated_learning_cross_device_example_common_roles, local.federated_learning_cross_device_example_workload_roles), local.federated_learning_cross_device_example_workload_kubernetes_service_accounts)

  federated_learning_cross_device_example_workloads_iam_members = {
    for entry in local.federated_learning_cross_device_example_workloads_iam_roles_setproduct : "${entry[0]}-${entry[1]}" => entry
  }
}

resource "google_project_iam_member" "workloads_roles" {
  for_each = local.federated_learning_cross_device_example_workloads_iam_members

  member  = each.value[1]
  project = data.google_project.cluster.project_id
  role    = each.value[0]
}
