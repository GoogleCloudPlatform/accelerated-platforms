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
  wi_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
}

resource "google_project_iam_member" "otel_collector" {
  for_each = toset([
    "roles/monitoring.metricWriter"
  ])

  member  = "${local.wi_principal_prefix}/ns/${local.otel_collector_kubernetes_namespace}/sa/${local.otel_collector_kubernetes_service_account}"
  project = google_project_service.anthosconfigmanagement_googleapis_com.project
  role    = each.value
}
