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
  endpoints_hostname_suffix = "endpoints.${data.google_project.cluster.project_id}.cloud.goog"

  endpoints = {
    gradio = {
      host         = "gradio.${var.fine_tuning_team_namespace}.${local.unique_identifier_prefix}.${local.endpoints_hostname_suffix}"
      port         = 8080
      service_name = "gradio-svc"
    },
    locust = {
      host         = "locust.${var.fine_tuning_team_namespace}.${local.unique_identifier_prefix}.${local.endpoints_hostname_suffix}"
      port         = 8089
      service_name = "locust-master-web-svc"
    },
    mlflow-tracking = {
      host         = "mlflow-tracking.${var.fine_tuning_team_namespace}.${local.unique_identifier_prefix}.${local.endpoints_hostname_suffix}"
      port         = 5000
      service_name = "mlflow-tracking-svc"
    },
    ray-dashboard = {
      host         = "ray-dashboard.${var.fine_tuning_team_namespace}.${local.unique_identifier_prefix}.${local.endpoints_hostname_suffix}"
      port         = 8265
      service_name = "ray-cluster-kuberay-head-svc"
    }
  }
}

resource "terraform_data" "endpoint_undelete" {
  for_each = local.endpoints

  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${each.value.host} --quiet >/dev/null 2>&1"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "endpoint" {
  depends_on = [
    terraform_data.endpoint_undelete,
  ]

  for_each = local.endpoints

  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = each.value.host,
      ip_address = google_compute_global_address.external_gateway_https.address,
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = each.value.host
}
