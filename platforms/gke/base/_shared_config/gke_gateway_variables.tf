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

locals {
  gke_l7_global_external_managed_cert_map_name        = "${local.unique_identifier_prefix}-gke-l7-global-external-managed"
  gke_l7_global_external_managed_endpoint             = "external.${local.unique_identifier_prefix}.endpoints.${data.google_project.cluster.project_id}.cloud.goog"
  gke_l7_global_external_managed_cert_name            = "${local.unique_identifier_prefix}-gke-l7-global-external-managed"
  gke_l7_global_external_managed_gateway_address_name = "${local.unique_identifier_prefix}-gke-l7-global-external-managed"
  gke_l7_global_external_managed_gateway_name         = "gke-l7-global-external-managed"

  gke_l7_regional_external_managed_cert_name            = "${local.unique_identifier_prefix}-gke-l7-${local.cluster_region}-external-managed"
  gke_l7_regional_external_managed_endpoint             = "${local.cluster_region}.external.${local.unique_identifier_prefix}.endpoints.${data.google_project.cluster.project_id}.cloud.goog"
  gke_l7_regional_external_managed_gateway_address_name = "${local.unique_identifier_prefix}-gke-l7-${local.cluster_region}-external-managed"
  gke_l7_regional_external_managed_gateway_name         = "gke-l7-${local.cluster_region}-external-managed"

  gke_l7_rilb_cert_name            = "${local.unique_identifier_prefix}-gke-l7-${local.cluster_region}-ilb"
  gke_l7_rilb_endpoint             = "${local.cluster_region}.internal.${local.unique_identifier_prefix}.endpoints.${data.google_project.cluster.project_id}.cloud.goog"
  gke_l7_rilb_gateway_address_name = "${local.unique_identifier_prefix}-gke-l7-${local.cluster_region}-ilb"
  gke_l7_rilb_gateway_name         = "gke-l7-${local.cluster_region}-ilb"
}

variable "gke_gateway_kubernetes_namespace_name" {
  default     = "gke-gateway"
  description = "Namespace for the GKE gateway resources."
  type        = string
}
