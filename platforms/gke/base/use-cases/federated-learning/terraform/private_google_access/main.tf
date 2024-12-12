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
  # See https://cloud.google.com/vpc/docs/configure-private-google-access#config-domain
  private_google_access_ips = [
    "199.36.153.8", "199.36.153.9", "199.36.153.10", "199.36.153.11"
  ]

  private_google_access_zones = {
    private_google_apis = {
      name        = "private-google-apis"
      dns_name    = "googleapis.com."
      description = "Private DNS zone for Google APIs"
      record_sets = [
        {
          name = "*"
          type = "CNAME"
          ttl  = 300
          records = [
            "private.googleapis.com.",
          ]
        },
        {
          name    = "private"
          type    = "A"
          ttl     = 300
          records = local.private_google_access_ips
        },
      ]
    },
    container_registry = {
      name        = "private-google-access-container-registry"
      dns_name    = "gcr.io."
      description = "Private DNS zone for Container Registry"
      record_sets = [
        {
          name = "*"
          type = "CNAME"
          ttl  = 300
          records = [
            "gcr.io.",
          ]
        },
        {
          name    = ""
          type    = "A"
          ttl     = 300
          records = local.private_google_access_ips
        },
      ]
    },
    artifact_registry = {
      name        = "private-google-access-artifact-registry"
      dns_name    = "pkg.dev."
      description = "Private DNS zone for Artifact Registry"
      record_sets = [
        {
          name = "*"
          type = "CNAME"
          ttl  = 300
          records = [
            "pkg.dev.",
          ]
        },
        {
          name    = ""
          type    = "A"
          ttl     = 300
          records = local.private_google_access_ips
        },
      ]
    }
  }

  # Build a flat list of objects from a nested list of lists of objects.
  private_google_access_zones_records = flatten([
    for zone_name, zone in local.private_google_access_zones : [
      for record_set in zone.record_sets : {
        managed_zone = zone_name
        name         = record_set.name != "" ? "${record_set.name}.${zone.dns_name}" : zone.dns_name
        type         = record_set.type
        ttl          = record_set.ttl
        rrdatas      = record_set.records
      }
    ]
  ])
}

data "google_compute_network" "main_vpc_network" {
  name    = local.network_name
  project = google_project_service.dns_googleapis_com.project
}

resource "google_dns_managed_zone" "private_google_access" {
  for_each = local.private_google_access_zones

  project     = google_project_service.dns_googleapis_com.project
  name        = each.value.name
  dns_name    = each.value.dns_name
  description = each.value.description
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = data.google_compute_network.main_vpc_network.id
    }
  }
}

resource "google_dns_record_set" "private_google_access" {
  for_each = tomap({
    for private_google_access_zone_records in local.private_google_access_zones_records : "${private_google_access_zone_records.managed_zone}.${private_google_access_zone_records.name}.${private_google_access_zone_records.type}" => private_google_access_zone_records
  })

  managed_zone = google_dns_managed_zone.private_google_access[each.value.managed_zone].name
  project      = google_project_service.dns_googleapis_com.project
  name         = each.value.name
  type         = each.value.type
  ttl          = each.value.ttl
  rrdatas      = each.value.rrdatas
}
