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

module "alloydb_cluster" {
  source = "./alloydb/"

  cluster_id       = var.cluster_name
  cluster_location = var.region
  project_id       = var.project_id

  network_self_link  = "projects/${var.project_id}/global/networks/${var.network_name}"
  allocated_ip_range = google_compute_global_address.private_ip_alloc.name

  primary_instance = {
    instance_id        = "${var.primary_instance_name}",
    require_connectors = false
    ssl_mode           = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
    database_flags = {
      "alloydb.iam_authentication"                 = "on"
      "google_ml_integration.enable_model_support" = "on"
      "password.enforce_complexity"                = "on"
    }
  }

  depends_on = [
    google_service_networking_connection.vpc_connection,
  ]
}
