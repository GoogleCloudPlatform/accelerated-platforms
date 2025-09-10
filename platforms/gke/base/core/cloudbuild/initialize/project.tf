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

data "google_project" "artifact_registry" {
  project_id = local.cloudbuild_ar_project_id
}

data "google_project" "cloudbuild" {
  project_id = local.cloudbuild_project_id
}

resource "google_project_service" "artifact_registry" {
  for_each = toset([
    "artifactregistry.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.artifact_registry.project_id
  service                    = each.key
}

resource "google_project_service" "cloudbuild" {
  for_each = toset([
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cloudbuild.project_id
  service                    = each.key
}

resource "google_project_iam_member" "cloudbuild_cloudbuild_builds_builder" {
  for_each = toset([
    local.cloudbuild_service_account_member
  ])

  member  = each.key
  project = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  role    = "roles/cloudbuild.builds.builder"
}

resource "terraform_data" "wait_for_artifactregistry_api" {
  input = {
    project = google_project_service.artifact_registry["artifactregistry.googleapis.com"].project
  }

  provisioner "local-exec" {
    command     = <<EOT
retries=24
while ! gcloud artifacts repositories list --project=${self.input.project} --quiet >/dev/null 2>&1 ; do
  if ((retries = 0)); then
    exit 1
  fi
  echo "Waiting for Artifact Registry API to be enabled..."
  retries=$((retries - 1))
  sleep 5
done 
echo "Artifact Registry API is enabled!"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    project = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  }
}

resource "terraform_data" "wait_for_cloudbuild_api" {
  input = {
    project = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  }

  provisioner "local-exec" {
    command     = <<EOT
retries=24
while ! gcloud builds list --project=${self.input.project} --quiet >/dev/null 2>&1 ; do
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
    project = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  }
}

resource "terraform_data" "wait_for_secretmanager_api" {
  input = {
    project = google_project_service.cloudbuild["secretmanager.googleapis.com"].project
  }

  provisioner "local-exec" {
    command     = <<EOT
retries=24
successes=0
while [[ $${successes} -lt 5 ]]; do
    echo "Waiting for Secret Manager API to be enabled..."
    while ! gcloud secrets list --project=${self.input.project} --quiet >/dev/null 2>&1; do
      if ((retries = 0)); then
        exit 1
      fi
      retries=$((retries - 1))
      sleep 5
    done
    successes=$((successes + 1))
    sleep 5 
done
echo "Secret Manager API is enabled!"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    project = google_project_service.cloudbuild["secretmanager.googleapis.com"].project
  }
}
