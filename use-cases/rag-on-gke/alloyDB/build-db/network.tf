/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

data "google_compute_network" "default" {
  name    = var.network_name
  project = var.project_id
}


resource "google_compute_global_address" "private_ip_alloc" {
  project       = var.project_id
  name          = "adb-psa"
  address_type  = "INTERNAL"
  purpose       = "VPC_PEERING"
  prefix_length = var.alloydb_ip_prefix
  network       = data.google_compute_network.default.id
  address       = var.alloydb_ip_range 
}

resource "google_service_networking_connection" "vpc_connection" {
  network                 = data.google_compute_network.default.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
  deletion_policy         = "ABANDON"
}
