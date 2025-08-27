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

resource "google_workstations_workstation_cluster" "cluster" {
  depends_on = [
    google_project_service.workstation_cluster["workstations.googleapis.com"]
  ]

  provider = google-beta

  location               = local.workstation_cluster_region
  network                = data.google_compute_network.vpc.id
  subnetwork             = data.google_compute_subnetwork.region.id
  project                = data.google_project.workstation_cluster.project_id
  workstation_cluster_id = local.workstation_cluster_name
}
