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

output "federated_learning_tenant_apps_service_accounts_iam_emails" {
  description = "List of apps service accounts IAM emails"
  value       = local.apps_service_account_iam_emails
}

output "federated_learning_kubernetes_service_account_name" {
  description = "Kubernetes service account name used by federated learning workloads"
  value       = local.tenant_apps_kubernetes_service_account_name
}

output "workload_identity_principal_prefix" {
  description = "Workload identity principal prefix"
  value       = "principal://iam.googleapis.com/projects/${data.google_project.default.number}/locations/global/workloadIdentityPools/${data.google_project.default.project_id}.svc.id.goog/subject"
}
