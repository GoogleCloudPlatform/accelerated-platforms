/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


module "alloydb_central" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 3.0"

  cluster_id       = "cluster-${var.region_central}"
  cluster_location = var.region_central
  project_id       = var.project_id

  network_self_link           = "projects/${var.project_id}/global/networks/${var.network_name}"
  allocated_ip_range          = google_compute_global_address.private_ip_alloc.name
  cluster_encryption_key_name = google_kms_crypto_key.key_region_central.id

  automated_backup_policy = {
    location      = var.region_central
    backup_window = "1800s"
    enabled       = true
    weekly_schedule = {
      days_of_week = ["FRIDAY"],
      start_times  = ["2:00:00:00", ]
    }
    quantity_based_retention_count = 1
    time_based_retention_count     = null
    labels = {
      test = "alloydb-cluster-with-prim"
    }
    backup_encryption_key_name = google_kms_crypto_key.key_region_central.id
  }

  continuous_backup_recovery_window_days = 10
  continuous_backup_encryption_key_name  = google_kms_crypto_key.key_region_central.id

  primary_instance = {
    instance_id        = "cluster-${var.region_central}-instance1",
    require_connectors = false
    ssl_mode           = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    database_flags     = {
      "alloydb.iam_authentication" = "on"
      "google_ml_integration.enable_model_support" = "on"
      "password.enforce_complexity" = "on"
    }
  }

  read_pool_instance = [
    {
      instance_id        = "cluster-${var.region_central}-r1"
      display_name       = "cluster-${var.region_central}-r1"
      require_connectors = false
      ssl_mode           = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    }
  ]

  depends_on = [
    google_service_networking_connection.vpc_connection,
    google_kms_crypto_key_iam_member.alloydb_sa_iam,
  ]
}

resource "google_service_account" "alloydb_superuser_sa" {
  account_id   = "alloydb-superuser"
  display_name = "AlloyDB Super User SA"
  project = var.project_id
}

resource "google_alloydb_user" "superuser" {
  cluster = module.alloydb_central.cluster_id
  user_id = "${google_service_account.alloydb_superuser_sa.account_id}@${var.project_id}.iam"
  user_type = "ALLOYDB_IAM_USER"
  database_roles = [
    "alloydbsuperuser",
    "alloydbiamuser"
  ]
  depends_on = [module.alloydb_central]
}

resource "google_service_account" "alloydb_raguser_sa" {
  account_id   = "alloydb-raguser"
  display_name = "AlloyDB User SA"
  project = var.project_id
}

resource "google_alloydb_user" "ragusr" {
  cluster = module.alloydb_central.cluster_id
  user_id = "${google_service_account.alloydb_raguser_sa.account_id}@${var.project_id}.iam"
  user_type = "ALLOYDB_IAM_USER"
  database_roles = [
    "alloydbiamuser"
  ]  
  depends_on = [module.alloydb_central]
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


