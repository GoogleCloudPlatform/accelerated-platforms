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

resource "terraform_data" "endpoint_undelete" {
  for_each = local.mft_endpoints

  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${each.value.host} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "endpoint" {
  depends_on = [
    terraform_data.endpoint_undelete,
  ]

  for_each = local.mft_endpoints

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
