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

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "google_project" "comfyui_iap_oath_branding" {
  project_id = local.comfyui_iap_oath_branding_project_id
}

resource "google_project_service" "cluster" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "iap.googleapis.com",
    "texttospeech.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cluster.project_id
  service                    = each.key
}

# Create all project-level aiplatform.googleapis.com service agents
resource "google_project_service_identity" "aiplatform_service_agents" {
  provider = google-beta
  project  = data.google_project.cluster.project_id
  service  = "aiplatform.googleapis.com"
}

