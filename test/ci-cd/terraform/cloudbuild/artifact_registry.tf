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

resource "google_artifact_registry_repository" "ci_cd" {
  format        = "DOCKER"
  location      = var.build_location
  project       = data.google_project.build.project_id
  repository_id = "ci-cd"

  cleanup_policies {
    action = "DELETE"
    id     = "Delete untagged images"

    condition {
      tag_state = "UNTAGGED"
    }
  }

  docker_config {
    immutable_tags = false
  }

  lifecycle {
    ignore_changes = [
      labels
    ]
  }
}
