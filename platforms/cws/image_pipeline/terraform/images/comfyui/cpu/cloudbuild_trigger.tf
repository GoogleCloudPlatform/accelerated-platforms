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

resource "google_cloudbuild_trigger" "cws_image" {
  filename = "cloudbuild/comfyui-cpu.yaml"
  included_files = [
    "cloudbuild/comfyui-cpu.yaml",
    "container-images/comfyui/cpu/**",
  ]
  location        = local.cloudbuild_location
  name            = "${local.unique_identifier_prefix}-cws-image-comfyui-cpu"
  project         = data.google_project.cloudbuild.project_id
  service_account = data.google_service_account.cws_image_pipeline_build.id

  repository_event_config {
    repository = local.cloudbuild_cws_image_pipeline_git_repository_connection_id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }
}
