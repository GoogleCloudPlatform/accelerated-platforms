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
  alloydb_database_admin_iam_user = trimsuffix(google_service_account.alloydb_superuser.email, ".gserviceaccount.com")
  alloydb_database_admin_ksa      = "${var.environment_name}-${var.namespace}-db-admin"
  alloydb_user_iam_user           = trimsuffix(google_service_account.alloydb_user.email, ".gserviceaccount.com")
  alloydb_user_ksa                = "${var.environment_name}-${var.namespace}-db-user"
}

# ALLOYDB
###############################################################################
resource "google_project_service" "alloydb_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.environment.project_id
  service                    = "alloydb.googleapis.com"
}

resource "google_alloydb_cluster" "default" {
  cluster_id       = local.unique_identifier_prefix
  cluster_type     = "PRIMARY"
  database_version = "POSTGRES_15"
  deletion_policy  = "FORCE"
  location         = var.region
  project          = google_project_service.alloydb_googleapis_com.project

  psc_config {
    psc_enabled = true
  }
}

resource "google_alloydb_instance" "primary" {
  availability_type = "REGIONAL"
  cluster           = google_alloydb_cluster.default.name
  # https://cloud.google.com/alloydb/docs/reference/database-flags
  database_flags = {
    "alloydb.enable_pgaudit"      = "on"
    "alloydb.iam_authentication"  = "on"
    "password.enforce_complexity" = "on"
  }
  display_name  = "${local.unique_identifier_prefix}-primary"
  instance_id   = "${local.unique_identifier_prefix}-primary"
  instance_type = google_alloydb_cluster.default.cluster_type

  client_connection_config {
    require_connectors = false
    ssl_config {
      ssl_mode = "ENCRYPTED_ONLY"
    }
  }

  lifecycle {
    ignore_changes = [instance_type]
  }

  machine_config {
    cpu_count = 2
  }

  psc_instance_config {
    allowed_consumer_projects = [data.google_project.environment.number]
  }
}

# PSC CONSUMER
##############################################################################
resource "google_compute_address" "alloydb_psc_consumer_address" {
  address_type = "INTERNAL"
  name         = "${local.unique_identifier_prefix}-alloydb-psc"
  project      = data.google_project.environment.project_id
  region       = var.region
  subnetwork   = google_compute_subnetwork.default.name
}

resource "google_compute_forwarding_rule" "alloydb_psc_fwd_rule_consumer" {
  allow_psc_global_access = true
  ip_address              = google_compute_address.alloydb_psc_consumer_address.id
  load_balancing_scheme   = "" # need to override EXTERNAL default when target is a service attachment
  name                    = "${local.unique_identifier_prefix}-alloydb-psc-fwd-rule-consumer-endpoint"
  network                 = google_compute_network.default.name
  project                 = data.google_project.environment.project_id
  region                  = var.region
  target                  = google_alloydb_instance.primary.psc_instance_config[0].service_attachment_link
}

resource "google_dns_response_policy" "network" {
  project              = data.google_project.environment.project_id
  response_policy_name = "${local.unique_identifier_prefix}-rp"

  networks {
    network_url = google_compute_network.default.id
  }
}

resource "google_dns_response_policy_rule" "alloydb_primary_psc_dns_name" {
  dns_name        = google_alloydb_instance.primary.psc_instance_config[0].psc_dns_name
  project         = data.google_project.environment.project_id
  response_policy = google_dns_response_policy.network.response_policy_name
  rule_name       = "${google_alloydb_instance.primary.instance_id}-psc-dns-name"

  local_data {
    local_datas {
      name    = google_alloydb_instance.primary.psc_instance_config[0].psc_dns_name
      rrdatas = [google_compute_address.alloydb_psc_consumer_address.address]
      ttl     = 300
      type    = "A"
    }
  }
}

# GSA
###############################################################################
resource "google_service_account" "alloydb_superuser" {
  account_id   = "wi-${local.unique_identifier_prefix}-db-admin"
  display_name = "${local.unique_identifier_prefix} AlloyDB Superuser"
  project      = data.google_project.environment.project_id
}

resource "google_service_account" "alloydb_user" {
  account_id   = "wi-${local.unique_identifier_prefix}-db-user"
  display_name = "${local.unique_identifier_prefix} AlloyDB User"
  project      = data.google_project.environment.project_id
}

# KSA
###############################################################################
resource "kubernetes_service_account_v1" "alloydb_database_admin" {
  depends_on = [
    null_resource.namespace_manifests,
  ]

  metadata {
    annotations = {
      "iam.gke.io/gcp-service-account" = "${google_service_account.alloydb_superuser.email}"
    }
    name      = local.alloydb_database_admin_ksa
    namespace = var.namespace
  }
}

resource "kubernetes_service_account_v1" "alloydb_user" {
  depends_on = [
    null_resource.namespace_manifests,
  ]

  metadata {
    annotations = {
      "iam.gke.io/gcp-service-account" = "${google_service_account.alloydb_user.email}"
    }
    name      = local.alloydb_user_ksa
    namespace = var.namespace
  }
}

# ALLOYDB USER
###############################################################################
resource "google_alloydb_user" "superuser" {
  cluster = google_alloydb_instance.primary.cluster
  database_roles = [
    "alloydbiamuser",
    "alloydbsuperuser",
  ]
  user_id   = local.alloydb_database_admin_iam_user
  user_type = "ALLOYDB_IAM_USER"
}

resource "google_alloydb_user" "user" {
  cluster = google_alloydb_instance.primary.cluster
  database_roles = [
    "alloydbiamuser",
  ]
  user_id   = local.alloydb_user_iam_user
  user_type = "ALLOYDB_IAM_USER"
}

# IAM
###############################################################################
resource "google_project_iam_member" "alloydb_superuser_alloydb_client" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_superuser.member
  role    = "roles/alloydb.client"
}

resource "google_project_iam_member" "alloydb_superuser_alloydb_database_user" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_superuser.member
  role    = "roles/alloydb.databaseUser"
}

resource "google_project_iam_member" "alloydb_superuser_service_usage_consumer" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_superuser.member
  role    = "roles/serviceusage.serviceUsageConsumer"
}

resource "google_project_iam_member" "alloydb_user_alloydb_client" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_user.member
  role    = "roles/alloydb.client"
}

resource "google_project_iam_member" "alloydb_user_alloydb_database_user" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_user.member
  role    = "roles/alloydb.databaseUser"
}

resource "google_project_iam_member" "alloydb_user_service_usage_consumer" {
  project = data.google_project.environment.project_id
  member  = google_service_account.alloydb_user.member
  role    = "roles/serviceusage.serviceUsageConsumer"
}

resource "google_service_account_iam_member" "alloydb_superuser_workload_identity_user" {
  depends_on = [
    google_container_cluster.mlp,
    google_project_service.compute_googleapis_com,
  ]

  service_account_id = google_service_account.alloydb_superuser.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.wi_member_principal_prefix}/${local.alloydb_database_admin_ksa}"
}

resource "google_service_account_iam_member" "alloydb_user_workload_identity_user" {
  depends_on = [
    google_container_cluster.mlp,
    google_project_service.compute_googleapis_com,
  ]

  service_account_id = google_service_account.alloydb_user.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.wi_member_principal_prefix}/${local.alloydb_user_ksa}"
}

# TODO: This should be removed when functionality is run as the alloydb_user, not the alloydb_superuser
resource "google_storage_bucket_iam_member" "data_bucket_alloydb_superuser_storage_object_viewer" {
  bucket = google_storage_bucket.data.name
  member = google_service_account.alloydb_superuser.member
  role   = "roles/storage.objectViewer"
}

resource "google_storage_bucket_iam_member" "data_bucket_alloydb_user_storage_object_viewer" {
  bucket = google_storage_bucket.data.name
  member = google_service_account.alloydb_user.member
  role   = "roles/storage.objectViewer"
}
