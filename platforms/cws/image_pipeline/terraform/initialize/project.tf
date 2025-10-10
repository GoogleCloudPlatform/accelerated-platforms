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

data "google_project" "image_pipeline_git_token" {
  project_id = local.cloudbuild_cws_image_pipeline_git_token_project_id
}

resource "google_project_service" "cloudbuild" {
  for_each = toset(
    [
      "artifactregistry.googleapis.com",
      "cloudbuild.googleapis.com",
      "cloudscheduler.googleapis.com",
      "secretmanager.googleapis.com",
    ]
  )

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cloudbuild.project_id
  service                    = each.value
}

resource "google_project_service" "image_pipeline_git_token" {
  for_each = toset(
    [
      "secretmanager.googleapis.com",
    ]
  )

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.image_pipeline_git_token.project_id
  service                    = each.value
}

resource "google_project_service_identity" "cloudbuild" {
  for_each = toset(
    [
      "cloudbuild.googleapis.com",
    ]
  )

  provider = google-beta

  project = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  service = each.value
}

resource "terraform_data" "wait_for_cloudbuild_service_identity" {
  depends_on = [
    google_project_service_identity.cloudbuild["cloudbuild.googleapis.com"],
  ]

  input = {
    project_id = google_project_service.cloudbuild["cloudbuild.googleapis.com"].project
  }

  provisioner "local-exec" {
    command     = <<EOT
retries=24
while [[  "$(gcloud projects get-iam-policy ${self.input.project_id} --flatten="bindings[].members" --format="value(bindings.members)" --filter="bindings.role:roles/cloudbuild.serviceAgent" | wc -l)" == "0" ]]; do
  if ((retries = 0)); then
    exit 1
  fi
  echo "Waiting for Cloud Build service identities to be provisioned..."
  retries=$((retries - 1))
  sleep 5
done
echo "Cloud Build service identities have been provisioned!"
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}
