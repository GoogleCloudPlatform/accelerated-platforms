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

resource "google_artifact_registry_repository" "container_image_repository" {
  location      = var.cluster_region
  repository_id = "federated-learning-container-image-repository"
  description   = "Federated Learning container image repository"
  format        = "DOCKER"
  project       = google_project_service.artifactregistry_googleapis_com.project

  cleanup_policies {
    action = "DELETE"
    id     = "Delete untagged images"

    condition {
      tag_state = "UNTAGGED"
    }
  }
}
