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

resource "terraform_data" "gke_l7_global_external_managed_undelete" {
  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${local.gke_l7_global_external_managed_endpoint} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "terraform_data" "gke_l7_regional_external_managed_undelete" {
  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${local.gke_l7_regional_external_managed_endpoint} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "terraform_data" "gke_l7_rilb_undelete" {
  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${local.gke_l7_rilb_endpoint} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "gke_l7_global_external_managed" {
  depends_on = [
    terraform_data.gke_l7_global_external_managed_undelete,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.gke_l7_global_external_managed_endpoint
      ip_address = google_compute_global_address.gke_l7_global_external_managed_gateway.address
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = local.gke_l7_global_external_managed_endpoint
}

resource "google_endpoints_service" "gke_l7_regional_external_managed" {
  depends_on = [
    terraform_data.gke_l7_regional_external_managed_undelete,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.gke_l7_regional_external_managed_endpoint
      ip_address = google_compute_address.gke_l7_regional_external_managed.address
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = local.gke_l7_regional_external_managed_endpoint
}

resource "google_endpoints_service" "gke_l7_rilb" {
  depends_on = [
    terraform_data.gke_l7_rilb_undelete,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.gke_l7_rilb_endpoint
      ip_address = "192.168.0.1" # TODO: needs to be pulled from gateway
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = local.gke_l7_rilb_endpoint
}
