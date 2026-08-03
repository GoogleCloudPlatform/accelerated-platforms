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

data "google_compute_network" "vpc" {
  name    = local.network_cluster_network_name
  project = data.google_project.cluster.project_id
}

# Create an internal IP range reserved for Lustre VPC peering.
resource "google_compute_global_address" "lustre_ip_range" {
  depends_on    = [google_project_service.servicenetworking_googleapis_com]
  project       = data.google_project.cluster.project_id
  name          = "${local.unique_identifier_prefix}-lustre-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = data.google_compute_network.vpc.id
}

# Establish a private VPC connection to Google's service networking.
resource "google_service_networking_connection" "lustre_peering" {
  network                 = data.google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.lustre_ip_range.name]
}

# Create a firewall rule to allow Lustre traffic from the peering range.
resource "google_compute_firewall" "allow_lustre" {
  project = data.google_project.cluster.project_id
  name    = "${local.unique_identifier_prefix}-allow-lustre"
  network = data.google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["988", "6988"]
  }

  source_ranges = ["${google_compute_global_address.lustre_ip_range.address}/${google_compute_global_address.lustre_ip_range.prefix_length}"]
}
