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

resource "google_service_account" "alloydb_superuser_sa" {
  account_id   = "alloydb-superuser"
  display_name = "AlloyDB Super User SA"
  project      = var.project_id
}

resource "google_alloydb_user" "superuser" {
  cluster   = module.alloydb_cluster.cluster_id
  user_id   = "${google_service_account.alloydb_superuser_sa.account_id}@${var.project_id}.iam"
  user_type = "ALLOYDB_IAM_USER"
  database_roles = [
    "alloydbsuperuser",
    "alloydbiamuser"
  ]
  depends_on = [module.alloydb_cluster]
}

resource "google_service_account" "alloydb_raguser_sa" {
  account_id   = "alloydb-raguser"
  display_name = "AlloyDB User SA"
  project      = var.project_id
}

resource "google_alloydb_user" "ragusr" {
  cluster   = module.alloydb_cluster.cluster_id
  user_id   = "${google_service_account.alloydb_raguser_sa.account_id}@${var.project_id}.iam"
  user_type = "ALLOYDB_IAM_USER"
  database_roles = [
    "alloydbiamuser"
  ]
  depends_on = [module.alloydb_cluster]
}

resource "google_project_iam_binding" "databaseuser" {
  project = var.project_id
  role    = "roles/alloydb.databaseUser"

  members = [
    "serviceAccount:${google_service_account.alloydb_superuser_sa.email}",
    "serviceAccount:${google_service_account.alloydb_raguser_sa.email}",
  ]
}

resource "google_project_iam_binding" "serviceusage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"

  members = [
    "serviceAccount:${google_service_account.alloydb_superuser_sa.email}",
    "serviceAccount:${google_service_account.alloydb_raguser_sa.email}",
  ]
}
