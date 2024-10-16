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

module "alloydb_east" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 3.0"

  primary_cluster_name = module.alloydb_central.cluster_name ## Comment this line to promote this cluster as primary cluster

  cluster_id       = "cluster-${var.region_east}"
  cluster_location = var.region_east
  project_id       = var.project_id

  network_self_link           = "projects/${var.project_id}/global/networks/${var.network_name}"
  cluster_encryption_key_name = google_kms_crypto_key.key_region_east.id

  primary_instance = {
    instance_id = "cluster-${var.region_east}-instance1",

    client_connection_config = {
      require_connectors = false
      ssl_config         = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    }
  }

  continuous_backup_recovery_window_days = 10
  continuous_backup_encryption_key_name  = google_kms_crypto_key.key_region_east.id

  automated_backup_policy = {
    location      = var.region_east
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
    backup_encryption_key_name = google_kms_crypto_key.key_region_east.id
  }

  depends_on = [
    module.alloydb_central,
    google_service_networking_connection.vpc_connection,
    google_kms_crypto_key_iam_member.alloydb_sa_iam_secondary,
  ]
}

