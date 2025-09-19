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

# resource "google_certificate_manager_certificate_map" "gke_l7_global_external_managed" {
#   description = "${local.unique_identifier_prefix} gke-l7-global-external-managed gateway certificate map"
#   name        = local.gke_l7_global_external_managed_cert_map_name
#   project     = data.google_project.cluster.project_id
# }

resource "google_compute_managed_ssl_certificate" "gke_l7_global_external_managed" {
  name    = local.gke_l7_global_external_managed_cert_name
  project = data.google_project.cluster.project_id

  managed {
    domains = [
      google_endpoints_service.gke_l7_global_external_managed.service_name,
    ]
  }
}

#
# Classic certificates do not support regional certificates
#

# resource "google_compute_managed_ssl_certificate" "gke_l7_regional_external_managed" {
#   name    = local.gke_l7_regional_external_managed_cert_name
#   project = data.google_project.cluster.project_id

#   managed {
#     domains = [
#       google_endpoints_service.gke_l7_regional_external_managed.service_name,
#     ]
#   }
# }

# resource "google_compute_managed_ssl_certificate" "gke_l7_rilb" {
#   name    = local.gke_l7_rilb_cert_name
#   project = data.google_project.cluster.project_id

#   managed {
#     domains = [
#       google_endpoints_service.gke_l7_rilb.service_name,
#     ]
#   }
# }
