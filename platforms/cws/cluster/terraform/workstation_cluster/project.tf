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

data "google_project" "cloudbuild" {
  project_id = local.cloudbuild_project_id
}

data "google_project" "workstation_cluster" {
  project_id = local.workstation_cluster_project_id
}

resource "google_project_service" "workstation_cluster" {
  for_each = toset(
    [
      "containerfilesystem.googleapis.com",
      "workstations.googleapis.com",
    ]
  )

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.workstation_cluster.project_id
  service                    = each.value
}

resource "google_project_iam_member" "vm_cws_workstation_cluster_project" {
  for_each = toset(
    [
      "roles/aiplatform.user",
      "roles/logging.logWriter",
      "roles/monitoring.metricWriter",
      "roles/workstations.serviceAgent",
    ]
  )

  member  = google_service_account.vm_cws.member
  project = data.google_project.workstation_cluster.project_id
  role    = each.value
}

resource "google_project_iam_member" "vm_cws_cloudbuild_project" {
  for_each = toset(
    [
      "roles/artifactregistry.reader",
    ]
  )

  member  = google_service_account.vm_cws.member
  project = data.google_project.cloudbuild.project_id
  role    = each.value
}
