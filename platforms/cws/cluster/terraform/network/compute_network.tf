# Copyright 2025 Google LLC
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

resource "google_compute_network" "vpc" {
  for_each = toset(var.cws_network_name == null ? ["managed"] : [])

  auto_create_subnetworks = false
  name                    = local.cws_network_name
  project                 = google_project_service.workstation_cluster["compute.googleapis.com"].project
  routing_mode            = var.cws_network_routing_mode
}

data "google_compute_network" "vpc" {
  depends_on = [google_compute_network.vpc]

  name    = local.cws_network_name
  project = google_project_service.workstation_cluster["compute.googleapis.com"].project
}

resource "google_compute_subnetwork" "region" {
  for_each = toset(var.cws_subnetwork_name == null ? ["managed"] : [])

  ip_cidr_range            = var.cws_subnetwork_ip_cidr_range
  name                     = local.cws_subnetwork_name
  network                  = data.google_compute_network.vpc.id
  private_ip_google_access = true
  project                  = data.google_compute_network.vpc.project
  region                   = local.workstation_cluster_region
}

data "google_compute_subnetwork" "region" {
  depends_on = [
    google_compute_subnetwork.region,
  ]

  name    = local.cws_subnetwork_name
  project = data.google_compute_network.vpc.project
  region  = local.workstation_cluster_region
}

resource "google_compute_router" "router" {
  for_each = toset(var.cws_router_name == null ? ["managed"] : [])

  name    = local.cws_router_name
  network = data.google_compute_network.vpc.name
  project = data.google_compute_network.vpc.project
  region  = local.workstation_cluster_region
}

data "google_compute_router" "router" {
  depends_on = [
    google_compute_router.router,
  ]

  name    = local.cws_router_name
  network = data.google_compute_network.vpc.name
  project = data.google_compute_network.vpc.project
  region  = local.workstation_cluster_region
}

resource "google_compute_router_nat" "nat_gateway" {
  for_each = toset(var.cws_nat_gateway_name == null ? ["managed"] : [])

  name                               = local.cws_nat_gateway_name
  nat_ip_allocate_option             = "AUTO_ONLY"
  project                            = data.google_compute_network.vpc.project
  region                             = local.workstation_cluster_region
  router                             = data.google_compute_router.router.name
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

data "google_compute_router_nat" "nat_gateway" {
  depends_on = [
    google_compute_router_nat.nat_gateway,
  ]

  name    = local.cws_nat_gateway_name
  project = data.google_compute_network.vpc.project
  region  = local.workstation_cluster_region
  router  = data.google_compute_router.router.name
}

data "google_netblock_ip_ranges" "iap_forwarders" {
  range_type = "iap-forwarders"
}

resource "google_compute_firewall" "iap-allow" {
  name          = "${local.unique_identifier_prefix}-iap"
  network       = data.google_compute_network.vpc.id
  project       = google_project_service.workstation_cluster["compute.googleapis.com"].project
  source_ranges = data.google_netblock_ip_ranges.iap_forwarders.cidr_blocks

  allow {
    protocol = "tcp"
    ports    = ["22", "3389", ]
  }
}

