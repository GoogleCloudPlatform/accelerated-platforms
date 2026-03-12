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
  # Path to your JSON file
  dashboard_json = "${path.module}/templates/dashboard/llmd_dashboard.json"
}

resource "google_monitoring_dashboard" "llm_dashboard" {
  project = data.google_project.cluster.project_id
  dashboard_json = templatefile(local.dashboard_json, {
    namespace    = var.llmd_kubernetes_namespace
    cluster_name = local.cluster_name
    location     = local.cluster_region
  })
}
