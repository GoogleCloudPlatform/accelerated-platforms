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

locals {
  # private_google_access_netblock_ip_range returns lists of network address blocks in CIDR notation (e.g. ["199.36.153.8/30"])
  # We first iterate over each block.
  # For each block, we compute how many IP addresses are in that block, and we use the cidrhost function to extract IP addresses
  # from the block.
  # Finally, we use the flatten function to have a list of IP addresses.
  private_google_access_ips = flatten([
    for cidr in data.google_netblock_ip_ranges.private_google_access_netblock_ip_range.cidr_blocks_ipv4 : [
      for host_number in range(0, pow(2, 32 - parseint(split("/", cidr)[1], 10))) :
      cidrhost(cidr, host_number)
    ]
  ])
}

data "google_netblock_ip_ranges" "private_google_access_netblock_ip_range" {
  range_type = "private-googleapis"
}

data "google_compute_network" "main_vpc_network" {
  name    = local.network_cluster_network_name
  project = google_project_service.dns_googleapis_com.project
}

resource "google_dns_managed_zone" "private_google_access" {
  description = "Private DNS zone for Google APIs"
  dns_name    = "googleapis.com."
  name        = "${local.unique_identifier_prefix}-private-google-apis"
  project     = google_project_service.dns_googleapis_com.project
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.main_vpc_network.id
    }
  }
}

resource "google_dns_managed_zone" "private_google_access_container_registry" {
  description = "Private DNS zone for Container Registry"
  dns_name    = "gcr.io."
  name        = "${local.unique_identifier_prefix}-private-google-access-container-registry"
  project     = google_project_service.dns_googleapis_com.project
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.main_vpc_network.id
    }
  }
}

resource "google_dns_managed_zone" "private_google_access_artifact_registry" {
  description = "Private DNS zone for Artifact Registry"
  dns_name    = "pkg.dev."
  name        = "${local.unique_identifier_prefix}-private-google-access-artifact-registry"
  project     = google_project_service.dns_googleapis_com.project
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.main_vpc_network.id
    }
  }
}

resource "google_dns_record_set" "private_google_access_cname" {
  managed_zone = google_dns_managed_zone.private_google_access.name
  name         = "*.${google_dns_managed_zone.private_google_access.dns_name}"
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "CNAME"

  rrdatas = [
    google_dns_record_set.private_google_access_a.name,
  ]
}

resource "google_dns_record_set" "private_google_access_a" {
  managed_zone = google_dns_managed_zone.private_google_access.name
  name         = "private.${google_dns_managed_zone.private_google_access.dns_name}"
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "A"

  rrdatas = local.private_google_access_ips
}

resource "google_dns_record_set" "private_google_access_container_registry_cname" {
  managed_zone = google_dns_managed_zone.private_google_access_container_registry.name
  name         = "*.${google_dns_managed_zone.private_google_access_container_registry.dns_name}"
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "CNAME"

  rrdatas = [
    google_dns_record_set.private_google_access_container_registry_a.name,
  ]
}

resource "google_dns_record_set" "private_google_access_container_registry_a" {
  managed_zone = google_dns_managed_zone.private_google_access_container_registry.name
  name         = google_dns_managed_zone.private_google_access_container_registry.dns_name
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "A"

  rrdatas = local.private_google_access_ips
}

resource "google_dns_record_set" "private_google_access_artifact_registry_cname" {
  managed_zone = google_dns_managed_zone.private_google_access_artifact_registry.name
  name         = "*.${google_dns_managed_zone.private_google_access_artifact_registry.dns_name}"
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "CNAME"

  rrdatas = [
    google_dns_record_set.private_google_access_artifact_registry_a.name,
  ]
}

resource "google_dns_record_set" "private_google_access_artifact_registry_a" {
  managed_zone = google_dns_managed_zone.private_google_access_artifact_registry.name
  name         = google_dns_managed_zone.private_google_access_artifact_registry.dns_name
  project      = google_project_service.dns_googleapis_com.project
  ttl          = 300
  type         = "A"

  rrdatas = local.private_google_access_ips
}
