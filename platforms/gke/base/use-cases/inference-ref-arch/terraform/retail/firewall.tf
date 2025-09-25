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

resource "google_compute_firewall" "dataflow_ingress" {
  name      = "dataflow-ingress"
  network   = local.network_cluster_network_name
  direction = "INGRESS"
  project   = data.google_project.cluster.project_id

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }

  source_tags = ["dataflow"]
  target_tags = ["dataflow"]
}

resource "google_compute_firewall" "dataflow_egress" {
  name      = "dataflow-egress"
  network   = local.network_cluster_network_name
  direction = "EGRESS"
  project   = data.google_project.cluster.project_id

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }

  destination_ranges = ["10.0.0.0/8"]
  target_tags        = ["dataflow"]
}
