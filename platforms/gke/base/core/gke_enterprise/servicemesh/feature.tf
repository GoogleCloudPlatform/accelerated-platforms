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

resource "google_gke_hub_feature" "servicemesh" {
  location = "global"
  name     = "servicemesh"
  project  = google_project_service.cluster["mesh.googleapis.com"].project

  fleet_default_member_config {
    mesh {
      management = "MANAGEMENT_AUTOMATIC"
    }
  }
}

resource "google_gke_hub_feature_membership" "cluster_servicemesh" {
  feature    = google_gke_hub_feature.servicemesh.name
  location   = google_gke_hub_feature.servicemesh.location
  membership = data.google_container_cluster.cluster.name
  project    = google_gke_hub_feature.servicemesh.project

  mesh {
    management = "MANAGEMENT_AUTOMATIC"
  }
}
