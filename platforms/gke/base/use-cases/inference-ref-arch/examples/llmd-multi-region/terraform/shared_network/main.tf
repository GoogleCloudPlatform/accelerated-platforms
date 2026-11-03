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

# Shared VPC for every regional cluster of the multi-region environment.
#
# The regional core platforms are deployed with
# `network_cluster_network_name = <this network>`, so core/networking creates
# only the regional node subnet, the REGIONAL_MANAGED_PROXY proxy-only subnet,
# the Cloud Router, and Cloud NAT. This module owns everything that is shared
# by, or spans, regions:
#   - the VPC network itself,
#   - one GLOBAL_MANAGED_PROXY proxy-only subnet per region, required by the
#     cross-region internal Application Load Balancer behind the
#     `gke-l7-cross-regional-internal-managed-mc` GatewayClass,
#   - firewall rules that let the load balancer proxies and Google Cloud
#     health checks reach the model servers.

locals {
  proxy_source_ranges = concat(
    [for r in var.regions : r.global_proxy_cidr],
    [for r in var.regions : r.regional_proxy_cidr],
  )
}

resource "google_project_service" "compute" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = var.project_id
  service                    = "compute.googleapis.com"
}

resource "google_compute_network" "vpc" {
  auto_create_subnetworks = false
  name                    = var.network_name
  project                 = google_project_service.compute.project
  routing_mode            = "GLOBAL"
}

resource "google_compute_subnetwork" "global_proxy" {
  for_each = var.regions

  ip_cidr_range = each.value.global_proxy_cidr
  name          = "${var.network_name}-${each.value.region}-gproxy"
  network       = google_compute_network.vpc.id
  project       = google_project_service.compute.project
  purpose       = "GLOBAL_MANAGED_PROXY"
  region        = each.value.region
  role          = "ACTIVE"
}

# Envoy-based load balancer proxies (regional and cross-region internal ALBs)
# connect to backends from the proxy-only subnets.
resource "google_compute_firewall" "allow_lb_proxies" {
  name      = "${var.network_name}-allow-lb-proxies"
  network   = google_compute_network.vpc.id
  project   = google_project_service.compute.project
  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = var.backend_ports
  }

  source_ranges = local.proxy_source_ranges
}

# Google Cloud health check probers.
# https://cloud.google.com/load-balancing/docs/health-check-concepts#ip-ranges
resource "google_compute_firewall" "allow_health_checks" {
  name      = "${var.network_name}-allow-health-checks"
  network   = google_compute_network.vpc.id
  project   = google_project_service.compute.project
  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = var.backend_ports
  }

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
}

# Internal traffic between the regional node subnets (benchmark clients in one
# region calling load balancer VIPs and pods in another region).
resource "google_compute_firewall" "allow_internal" {
  name      = "${var.network_name}-allow-internal"
  network   = google_compute_network.vpc.id
  project   = google_project_service.compute.project
  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [for r in var.regions : r.node_cidr]
}
