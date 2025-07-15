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

data "google_compute_lb_ip_ranges" "google" {
}

resource "google_compute_firewall" "workloads" {
  name        = join("-", [local.unique_identifier_prefix, "workloads"])
  description = "Allow connections to workloads from internal load balancer"
  network     = local.network_name
  project     = google_project_service.confidentialcomputing_googleapis_com.project

  # Workloads in confidential space are listening to port 8082
  allow {
    protocol = "tcp"
    ports    = ["8082"]
  }
  source_ranges = data.google_compute_lb_ip_ranges.google.http_ssl_tcp_internal
}

resource "google_compute_firewall" "ssh" {
  count       = var.federated_learning_cross_device_example_confidential_space_debug ? 1 : 0
  name        = join("-", [local.unique_identifier_prefix, "ssh"])
  description = "Allow SSH connections to confidential space VM for debugging purpose"
  network     = local.network_name
  project     = google_project_service.confidentialcomputing_googleapis_com.project

  # Opening SSH port for debugging purpose
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  source_ranges = ["0.0.0.0/0"]
}
