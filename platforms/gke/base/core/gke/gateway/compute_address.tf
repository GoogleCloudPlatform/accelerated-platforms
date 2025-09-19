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

resource "google_compute_global_address" "gke_l7_global_external_managed_gateway" {
  name    = local.gke_l7_global_external_managed_gateway_address_name
  project = data.google_project.cluster.project_id
}

resource "google_compute_address" "gke_l7_regional_external_managed" {
  name    = local.gke_l7_regional_external_managed_gateway_address_name
  project = data.google_project.cluster.project_id
  region  = local.cluster_region
}

# resource "google_compute_address" "gke_l7_rilb" {
#   name    = local.gke_l7_rilb_gateway_address_name
#   project = data.google_project.cluster.project_id
#   region  = local.cluster_region
# }
