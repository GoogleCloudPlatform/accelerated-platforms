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

resource "google_compute_network" "default" {
  auto_create_subnetworks = false
  name                    = local.unique_identifier_prefix
  project                 = data.google_project.environment.project_id
  routing_mode            = var.routing_mode
}

resource "google_compute_subnetwork" "default" {
  ip_cidr_range            = var.subnet_ip_cidr_range
  name                     = "${local.unique_identifier_prefix}-${var.region}"
  network                  = google_compute_network.default.id
  private_ip_google_access = true
  project                  = data.google_project.environment.project_id
  region                   = var.region
}

resource "google_compute_router" "default" {
  name    = local.unique_identifier_prefix
  network = google_compute_network.default.id
  project = data.google_project.environment.project_id
  region  = var.region

  bgp {
    asn = "64514"
  }
}

resource "google_compute_router_nat" "default" {
  name                               = local.unique_identifier_prefix
  nat_ip_allocate_option             = "AUTO_ONLY"
  project                            = data.google_project.environment.project_id
  region                             = var.region
  router                             = google_compute_router.default.name
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
