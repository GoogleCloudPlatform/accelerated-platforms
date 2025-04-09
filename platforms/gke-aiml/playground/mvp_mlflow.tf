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
  mlflow_ksa             = "${var.environment_name}-${var.namespace}-mlflow"
  bucket_mlflow_name      = "${data.google_project.environment.project_id}-${var.environment_name}-mlflow"
}

resource "google_storage_bucket" "mlflow" {
  depends_on = [
    google_container_cluster.mlp
  ]

  force_destroy               = true
  location                    = var.region
  name                        = local.bucket_mlflow_name
  project                     = data.google_project.environment.project_id
  uniform_bucket_level_access = true
}

# IAM
###############################################################################

resource "kubernetes_service_account_v1" "mlflow" {
  depends_on = [
    null_resource.namespace_manifests,
  ]
  metadata {
    name      = local.mlflow_ksa
    namespace = var.namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = "${google_service_account.alloydb_user.email}"
    }
  }
}

# MLFLOW
###########################################################

variable "roles_set" {
  type = list(string)
  default = ["roles/iam.workloadIdentityUser", "roles/iam.serviceAccountTokenCreator"]
}

resource "google_project_iam_member" "mlflow_ksa_user" {
  depends_on = [
    google_container_cluster.mlp
  ]
  for_each = toset(var.roles_set)
  project = data.google_project.environment.project_id
  member  = "${local.wi_member_principal_prefix}/${local.mlflow_ksa}"
  role    = each.value
}

# MLFLOW BUCKET
###########################################################

resource "google_storage_bucket_iam_member" "data_bucket_mlflow_storage_object_user" {
  bucket = google_storage_bucket.mlflow.name
  member = "${local.wi_member_principal_prefix}/${local.mlflow_ksa}"
  role   = "roles/storage.objectUser"
}
