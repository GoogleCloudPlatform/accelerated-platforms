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
  ate_cloudsql_connection_name = "${local.ate_cloudsql_project_id}:${local.ate_cloudsql_region}:${google_sql_database_instance.ate.name}"
  ate_db_iam_user              = trimsuffix(data.google_service_account.ate_api_server.email, ".gserviceaccount.com")
  ate_postgres_password        = substr(sha256(tls_private_key.postgres_password.private_key_pem), 0, 32)
}

resource "google_project_service" "sqladmin" {
  disable_on_destroy = false
  project            = local.ate_cloudsql_project_id
  service            = "sqladmin.googleapis.com"
}

resource "google_project_service" "servicenetworking" {
  disable_on_destroy = false
  project            = local.cluster_project_id
  service            = "servicenetworking.googleapis.com"
}

data "google_compute_network" "cluster" {
  name    = local.network_cluster_network_name
  project = local.cluster_project_id
}

resource "google_compute_global_address" "ate_sql_ip_range" {
  depends_on = [
    google_project_service.servicenetworking,
  ]

  address_type  = "INTERNAL"
  name          = "google-managed-services-${local.network_cluster_network_name}"
  network       = data.google_compute_network.cluster.id
  prefix_length = 16
  project       = local.cluster_project_id
  purpose       = "VPC_PEERING"
}

resource "google_service_networking_connection" "ate_sql_peering" {
  deletion_policy = "ABANDON"
  network         = data.google_compute_network.cluster.id
  reserved_peering_ranges = [
    google_compute_global_address.ate_sql_ip_range.name,
  ]
  service = "servicenetworking.googleapis.com"
}

resource "google_sql_database_instance" "ate" {
  depends_on = [
    google_project_service.sqladmin,
    google_service_networking_connection.ate_sql_peering,
  ]

  database_version    = "POSTGRES_18"
  deletion_protection = false
  name                = local.ate_cloudsql_instance_name
  project             = local.ate_cloudsql_project_id
  region              = local.ate_cloudsql_region

  settings {
    edition = var.ate_cloudsql_edition
    tier    = var.ate_cloudsql_tier

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = data.google_compute_network.cluster.id
    }
  }
}

resource "google_sql_database" "ate" {
  deletion_policy = "ABANDON"
  instance        = google_sql_database_instance.ate.name
  name            = "atepg"
  project         = local.ate_cloudsql_project_id
}

resource "google_sql_user" "ate_iam_user" {
  depends_on = [
    google_project_iam_member.ate_api_server_cloudsql_instance_user,
  ]

  deletion_policy = "ABANDON"
  instance        = google_sql_database_instance.ate.name
  name            = local.ate_db_iam_user
  project         = local.ate_cloudsql_project_id
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "tls_private_key" "postgres_password" {
  algorithm = "ED25519"
}

resource "google_sql_user" "postgres" {
  instance = google_sql_database_instance.ate.name
  name     = "postgres"
  password = local.ate_postgres_password
  project  = local.ate_cloudsql_project_id
}
