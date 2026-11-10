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

# One VPC network for every regional platform of a multi-region environment
# (NETWORK_MODE=shared-vpc).
#
# provision.sh deploys each regional platform with
# `network_cluster_network_name = <this network>`, so core/networking creates
# only the regional node subnet, the REGIONAL_MANAGED_PROXY proxy-only subnet,
# the Cloud Router, and Cloud NAT. This terraservice owns everything that is
# shared by, or spans, regions:
#   - the VPC network itself,
#   - one GLOBAL_MANAGED_PROXY proxy-only subnet per region, required by the
#     cross-region internal Application Load Balancer (global_lb) and by
#     multi-cluster Gateways,
#   - firewall rules that let the load balancer proxies, Google Cloud health
#     checks, and the nodes and Pods of every region reach each other.
#
# var.regions is the registry of the environment's platforms: provision.sh and
# teardown.sh read it back (output "regions") to add and remove platforms, and
# global_lb.sh reads it to create one VIP per region.

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
  direction = "INGRESS"
  name      = "${var.network_name}-allow-lb-proxies"
  network   = google_compute_network.vpc.id
  priority  = 1000
  project   = google_project_service.compute.project

  allow {
    ports    = var.backend_ports
    protocol = "tcp"
  }

  source_ranges = local.proxy_source_ranges
}

# Google Cloud health check probers.
# https://cloud.google.com/load-balancing/docs/health-check-concepts#ip-ranges
resource "google_compute_firewall" "allow_health_checks" {
  direction = "INGRESS"
  name      = "${var.network_name}-allow-health-checks"
  network   = google_compute_network.vpc.id
  priority  = 1000
  project   = google_project_service.compute.project

  allow {
    ports    = var.backend_ports
    protocol = "tcp"
  }

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
}

# Traffic between the node and Pod ranges of every region, for example clients
# in one region calling load balancer VIPs, or Pods in another region.
resource "google_compute_firewall" "allow_internal" {
  direction = "INGRESS"
  name      = "${var.network_name}-allow-internal"
  network   = google_compute_network.vpc.id
  priority  = 1000
  project   = google_project_service.compute.project

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = concat(
    [for r in var.regions : r.node_cidr],
    [for r in var.regions : r.pod_cidr],
  )
}

# GKE doesn't always delete the standalone NEGs of a Service when its cluster
# is deleted, and leftover NEGs block the deletion of the network. Same cleanup
# as core/networking runs for the networks that it manages.
resource "terraform_data" "neg_cleanup" {
  input = {
    network_self_link = google_compute_network.vpc.self_link
    project_id        = google_project_service.compute.project
  }

  provisioner "local-exec" {
    command     = <<EOT
echo "Cleaning up network endpoint groups..."
negs=$(gcloud compute network-endpoint-groups list --filter="network=${self.input.network_self_link}" --format='value(format("{0},{1}", name, zone.basename()))' --project=${self.input.project_id})
for neg in $${negs}; do
  name="$${neg%,*}"
  zone="$${neg#*,}"

  echo "Deleting '$${name}' network endpoint group in $${zone}..."
  gcloud compute network-endpoint-groups delete $${name} \
  --project=${self.input.project_id} \
  --quiet \
  --zone=$${zone}
done
EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }
}
