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
  cluster_wi_principal_prefix            = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  mlflow_kubernetes_namespace            = var.mlflow_kubernetes_namespace != null ? var.mlflow_kubernetes_namespace : "mlflow-system"
  mlflow_kubernetes_service_account_name = var.mlflow_kubernetes_service_account_name != null ? var.mlflow_kubernetes_service_account_name : "mlflow"
  mlflow_service_account_name            = var.mlflow_service_account_name != null ? var.mlflow_service_account_name : "${local.unique_identifier_prefix}-mlflow"
  mlflow_service_account_project_id      = var.mlflow_service_account_project_id != null ? var.mlflow_service_account_project_id : var.platform_default_project_id
  mlflow_service_account_email           = "${local.mlflow_service_account_name}@${local.mlflow_service_account_project_id}.iam.gserviceaccount.com"
  mlflow_wi_member                       = "${local.cluster_wi_principal_prefix}/ns/${local.mlflow_kubernetes_namespace}/sa/${local.mlflow_kubernetes_service_account_name}"
}

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

resource "google_service_account" "mlflow" {
  for_each = toset(var.mlflow_service_account_name == null ? ["managed"] : [])

  account_id   = local.mlflow_service_account_name
  display_name = "GCP Service Account for MLflow core tracking workload"
  project      = local.mlflow_service_account_project_id
}

data "google_service_account" "mlflow" {
  depends_on = [
    google_service_account.mlflow,
  ]

  account_id = local.mlflow_service_account_name
  project    = local.mlflow_service_account_project_id
}

resource "google_storage_bucket_iam_member" "mlflow" {
  bucket = data.google_storage_bucket.mlflow.name
  member = "serviceAccount:${data.google_service_account.mlflow.email}"
  role   = "roles/storage.objectAdmin"
}

resource "google_service_account_iam_member" "mlflow_workload_identity" {
  member             = local.mlflow_wi_member
  role               = "roles/iam.workloadIdentityUser"
  service_account_id = data.google_service_account.mlflow.id
}
