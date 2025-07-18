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

resource "google_project_service" "cloudbuild_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cloudbuild.project_id
  service                    = "cloudbuild.googleapis.com"
}

resource "google_project_service" "secretmanager_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cloudbuild.project_id
  service                    = "secretmanager.googleapis.com"
}

resource "terraform_data" "wait_for_cloudbuild_api" {
  input = {
    project = google_project_service.cloudbuild_googleapis_com.project
  }

  provisioner "local-exec" {
    command     = <<EOT
retries=24
while ! gcloud builds list --project=${self.input.project} >/dev/null 2>&1 --quiet; do
  if ((retries = 0)); then
    exit 1
  fi
  echo "Waiting for Cloud Build API to be enabled..."
  retries=$((retries - 1))
  sleep 5
done 
echo "Cloud Build API is enabled!"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    project = google_project_service.cloudbuild_googleapis_com.project
  }
}
