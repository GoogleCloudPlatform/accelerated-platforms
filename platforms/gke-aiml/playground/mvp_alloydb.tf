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

module "alloydb" {
  source = "../../../terraform/modules/alloydb_psc"

  cluster_id       = local.unique_identifier_prefix
  cluster_location = var.region
  project_id       = data.google_project.environment.project_id

  psc_enabled                   = true
  psc_allowed_consumer_projects = [data.google_project.environment.number]

  automated_backup_policy = {
    location      = var.region
    backup_window = "1800s"
    enabled       = true
    weekly_schedule = {
      days_of_week = ["FRIDAY"],
      start_times  = ["2:00:00:00", ]
    }
    quantity_based_retention_count = 1
    time_based_retention_count     = null
    labels                         = {}
  }

  continuous_backup_recovery_window_days = 10

  primary_instance = {
    instance_id        = "${local.unique_identifier_prefix}-instance1-psc",
    require_connectors = false
    ssl_mode           = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
  }

  read_pool_instance = [
    {
      instance_id        = "${local.unique_identifier_prefix}-r1-psc"
      display_name       = "${local.unique_identifier_prefix}-r1-psc"
      require_connectors = false
      ssl_mode           = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    }
  ]
}

# Create psc endpoint using alloydb psc attachment

resource "google_compute_network" "alloydb_psc" {
  auto_create_subnetworks = false
  name                    = "${local.unique_identifier_prefix}-alloydb-psc"
  project                 = data.google_project.environment.project_id
}

resource "google_compute_subnetwork" "alloydb_psc" {
  project       = data.google_project.environment.project_id
  name          = "${local.unique_identifier_prefix}-alloydb-psc-${var.region}"
  ip_cidr_range = "10.2.0.0/16"
  region        = var.region
  network       = google_compute_network.alloydb_psc.id
}

resource "google_compute_address" "alloydb_psc_consumer_address" {
  name    = "${local.unique_identifier_prefix}-alloydb-psc-address"
  project = data.google_project.environment.project_id
  region  = var.region

  subnetwork   = google_compute_subnetwork.alloydb_psc.name
  address_type = "INTERNAL"
  address      = "10.2.0.10"
}

resource "google_compute_forwarding_rule" "alloydb_psc_fwd_rule_consumer" {
  name    = "${local.unique_identifier_prefix}-alloydb-psc-fwd-rule-consumer-endpoint"
  region  = var.region
  project = data.google_project.environment.project_id

  target                  = module.alloydb.primary_instance.psc_instance_config[0].service_attachment_link
  load_balancing_scheme   = "" # need to override EXTERNAL default when target is a service attachment
  network                 = google_compute_network.alloydb_psc.name
  ip_address              = google_compute_address.alloydb_psc_consumer_address.id
  allow_psc_global_access = true
}
