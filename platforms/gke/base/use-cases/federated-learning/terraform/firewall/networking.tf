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
  project = google_project_service.compute_googleapis_com.project
}

data "google_compute_subnetwork" "region" {
  name    = local.subnetwork_name
  project = data.google_project.cluster.project_id
  region  = var.cluster_region
}

locals {
  cluster_subnetwork_secondary_ip_ranges = [for range in toset(data.google_compute_subnetwork.region.secondary_ip_range) : range.ip_cidr_range]
  master_ipv4_cidr_block                 = data.google_container_cluster.cluster.private_cluster_config[0].master_ipv4_cidr_block
}
