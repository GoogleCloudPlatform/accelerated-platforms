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
  project_id = var.cluster_project_id
}

data "google_project" "fine_tuning" {
  project_id = local.fine_tuning_project_id
}

data "google_project" "iap" {
  project_id = local.iap_project_id
}

resource "google_project_service" "aiplatform_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cluster.project_id
  service                    = "aiplatform.googleapis.com"
}

resource "google_project_service" "artifactregistry_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.fine_tuning.project_id
  service                    = "artifactregistry.googleapis.com"
}

resource "google_project_service" "certificatemanager_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cluster.project_id
  service                    = "certificatemanager.googleapis.com"
}

resource "google_project_service" "cloudbuild_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.fine_tuning.project_id
  service                    = "cloudbuild.googleapis.com"
}

resource "google_project_service" "iap_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.iap.project_id
  service                    = "iap.googleapis.com"
}
