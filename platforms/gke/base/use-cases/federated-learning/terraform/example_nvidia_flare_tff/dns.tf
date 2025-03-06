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

data "google_compute_network" "main_vpc_network" {
  name    = local.network_name
  project = data.google_project.default.project_id
}

resource "google_dns_managed_zone" "nvidia_flare_tff_example_dns_zone" {
  description = "Private DNS zone for the federated learning NVIDIA FLARE example"
  dns_name    = "${var.federated_learning_nvidia_flare_tff_example_domain}."
  name        = "${local.unique_identifier_prefix}-fl-nvflare"
  project     = data.google_project.default.project_id
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.main_vpc_network.id
    }
  }
}

resource "google_dns_record_set" "client1_a" {
  count = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") && length(var.federated_learning_nvidia_flare_tff_example_client1_a_rrdatas) > 0 ? 1 : 0

  managed_zone = google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.name
  name         = "client1.${google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.dns_name}"
  project      = data.google_project.default.project_id
  ttl          = 300
  type         = "A"

  rrdatas = var.federated_learning_nvidia_flare_tff_example_client1_a_rrdatas
}

resource "google_dns_record_set" "client2_a" {
  count = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") && length(var.federated_learning_nvidia_flare_tff_example_client2_a_rrdatas) > 0 ? 1 : 0

  managed_zone = google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.name
  name         = "client2.${google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.dns_name}"
  project      = data.google_project.default.project_id
  ttl          = 300
  type         = "A"

  rrdatas = var.federated_learning_nvidia_flare_tff_example_client2_a_rrdatas
}

resource "google_dns_record_set" "server1_a" {
  count = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "client") && length(var.federated_learning_nvidia_flare_tff_example_server1_a_rrdatas) > 0 ? 1 : 0

  managed_zone = google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.name
  name         = "server1.${google_dns_managed_zone.nvidia_flare_tff_example_dns_zone.dns_name}"
  project      = data.google_project.default.project_id
  ttl          = 300
  type         = "A"

  rrdatas = var.federated_learning_nvidia_flare_tff_example_server1_a_rrdatas
}
