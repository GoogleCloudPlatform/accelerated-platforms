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
  postgresdb_database_admin_iam_user = trimsuffix(google_service_account.postgresdb_superuser.email, ".gserviceaccount.com")
  postgresdb_database_admin_ksa      = "${var.environment_name}-${var.namespace}-db-admin"
  postgresdb_user_iam_user           = trimsuffix(google_service_account.postgresdb_user.email, ".gserviceaccount.com")
  postgresdb_user_ksa                = "${var.environment_name}-${var.namespace}-db-user"
}

# POSTGRESDB
###############################################################################
resource "google_project_service" "sqladmin_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.environment.project_id
  service                    = "sqladmin_googleapis_com"
}

resource "google_sql_database_instance" "mlflow_instance_prod" {
  name             = "mlflow-instance-prod"
  region           = var.region 
  database_version = "POSTGRES_17"
  settings {
    tier          = "db-perf-optimized-N-8"
    storage_auto_increase = true
    storage_size  = 50 * 1024 * 1024 * 1024 # Convert GB to bytes
    storage_type  = "SSD"
    ip_configuration {
      ipv4_enabled = false
      private_network = google_compute_network.default.name 
      private_ip_address = google_compute_global_address.private_ip_address.address # Use the reserved IP
    }
  }
  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.sqladmin_googleapis_com
  ]
}

resource "google_sql_database" "mlflow_database" {
  name     = "mlflow"
  instance = google_sql_database_instance.mlflow_instance_prod.name
  depends_on = [google_project_service.sqladmin_googleapis_com]
}

# PSC CONSUMER
##############################################################################
resource "google_compute_address" "postgres_psc_consumer_address" {
  address_type = "INTERNAL"
  name         = "${local.unique_identifier_prefix}-postgresdb-psc"
  project      = data.google_project.environment.project_id
  region       = var.region
  subnetwork   = google_compute_subnetwork.default.name
}

resource "google_compute_forwarding_rule" "postgresdb_psc_fwd_rule_consumer" {
  allow_psc_global_access = true
  ip_address              = google_compute_address.postgresdb_psc_consumer_address.id
  load_balancing_scheme   = "" # need to override EXTERNAL default when target is a service attachment
  name                    = "${local.unique_identifier_prefix}-postgresdb-psc-fwd-rule-consumer-endpoint"
  network                 = google_compute_network.default.name
  project                 = data.google_project.environment.project_id
  region                  = var.region
  target                  = google_postgresdb_instance.primary.psc_instance_config[0].service_attachment_link
}

resource "google_dns_response_policy" "network" {
  project              = data.google_project.environment.project_id
  response_policy_name = "${local.unique_identifier_prefix}-rp"

  networks {
    network_url = google_compute_network.default.id
  }
}

resource "google_dns_response_policy_rule" "postgresdb_primary_psc_dns_name" {
  dns_name        = google_postgresdb_instance.primary.psc_instance_config[0].psc_dns_name
  project         = data.google_project.environment.project_id
  response_policy = google_dns_response_policy.network.response_policy_name
  rule_name       = "${google_postgresdb_instance.primary.instance_id}-psc-dns-name"

  local_data {
    local_datas {
      name    = google_postgresdb_instance.primary.psc_instance_config[0].psc_dns_name
      rrdatas = [google_compute_address.postgresdb_psc_consumer_address.address]
      ttl     = 300
      type    = "A"
    }
  }
}

# GSA
###############################################################################
resource "google_service_account" "postgresdb_superuser" {
  account_id   = "wi-${local.unique_identifier_prefix}-db-admin"
  display_name = "${local.unique_identifier_prefix} AlloyDB Superuser"
  project      = data.google_project.environment.project_id
}

resource "google_service_account" "postgresdb_user" {
  account_id   = "wi-${local.unique_identifier_prefix}-db-user"
  display_name = "${local.unique_identifier_prefix} AlloyDB User"
  project      = data.google_project.environment.project_id
}

# KSA
###############################################################################
resource "kubernetes_service_account_v1" "postgresdb_database_admin" {
  depends_on = [
    null_resource.namespace_manifests,
  ]

  metadata {
    annotations = {
      "iam.gke.io/gcp-service-account" = "${google_service_account.postgresdb_superuser.email}"
    }
    name      = local.postgresdb_database_admin_ksa
    namespace = var.namespace
  }
}

resource "kubernetes_service_account_v1" "postgresdb_user" {
  depends_on = [
    null_resource.namespace_manifests,
  ]

  metadata {
    annotations = {
      "iam.gke.io/gcp-service-account" = "${google_service_account.postgresdb_user.email}"
    }
    name      = local.postgresdb_user_ksa
    namespace = var.namespace
  }
}

# POSGRESDB USER
###############################################################################
resource "google_postgresdb_user" "superuser" {
  cluster = google_postgresdb_instance.primary.cluster
  database_roles = [
    "postgresdbiamuser",
    "postgresdbsuperuser",
  ]
  user_id   = local.postgresdb_database_admin_iam_user
  user_type = "POSTGRESDB_IAM_USER"
}

resource "google_postgresdb_user" "user" {
  cluster = google_postgresdb_instance.primary.cluster
  database_roles = [
    "postgresdbiamuser",
  ]
  user_id   = local.postgresdb_user_iam_user
  user_type = "POSTGRESDB_IAM_USER"
}

# IAM
###############################################################################
resource "google_project_iam_member" "postgresdb_superuser_postgresdb_client" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_superuser.member
  role    = "roles/postgresdb.client"
}

resource "google_project_iam_member" "postgresdb_superuser_postgresdb_database_user" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_superuser.member
  role    = "roles/postgresdb.databaseUser"
}

resource "google_project_iam_member" "postgresdb_superuser_service_usage_consumer" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_superuser.member
  role    = "roles/serviceusage.serviceUsageConsumer"
}

resource "google_project_iam_member" "postgresdb_user_postgresdb_client" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_user.member
  role    = "roles/postgresdb.client"
}

resource "google_project_iam_member" "postgresdb_user_postgresdb_database_user" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_user.member
  role    = "roles/postgresdb.databaseUser"
}

resource "google_project_iam_member" "postgresdb_user_service_usage_consumer" {
  project = data.google_project.environment.project_id
  member  = google_service_account.postgresdb_user.member
  role    = "roles/serviceusage.serviceUsageConsumer"
}

resource "google_service_account_iam_member" "postgresdb_superuser_workload_identity_user" {
  service_account_id = google_service_account.postgresdb_superuser.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.wi_member_principal_prefix}/${local.postgresdb_database_admin_ksa}"
}

resource "google_service_account_iam_member" "postgresdb_user_workload_identity_user" {
  service_account_id = google_service_account.postgresdb_user.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.wi_member_principal_prefix}/${local.postgresdb_user_ksa}"
}

# TODO: This should be removed when functionality is run as the postgresdb_user, not the postgresdb_superuser
resource "google_storage_bucket_iam_member" "data_bucket_postgresdb_superuser_storage_object_viewer" {
  bucket = google_storage_bucket.data.name
  member = google_service_account.postgresdb_superuser.member
  role   = "roles/storage.objectViewer"
}

resource "google_storage_bucket_iam_member" "data_bucket_postgresdb_user_storage_object_viewer" {
  bucket = google_storage_bucket.data.name
  member = google_service_account.postgresdb_user.member
  role   = "roles/storage.objectViewer"
}
