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

locals {
  cloudbuild_submit_command    = "until gcloud builds submit --substitutions=_PROJECT_ID=\"${google_project_service.cloud_build_googleapis_com.project},_REGISTRY=${var.cluster_region}-docker.pkg.dev/${google_project_service.cloud_build_googleapis_com.project}/${local.federated_learning_repository_id}\" --region ${var.cluster_region}; do echo \"Building workloads images; sleep 5; done"
  cloudbuild_git_clone_command = "git clone --recurse-submodules https://github.com/privacysandbox/odp-federatedcompute --branch=${var.federated_learning_cross_device_example_federatedcompute_tag}; cd odp-federatedcompute; sed -i '29s/^#//;30s/^#//;31s/^#//' cloudbuild.yaml"
  cloudbuild_sa_roles = [
    "roles/storage.objectUser",
    "roles/logging.logWriter",
    "roles/artifactregistry.writer"
  ]
}

# Wait for Spanner API to be enabled
resource "terraform_data" "wait_for_cloud_build_api" {
  provisioner "local-exec" {
    command = <<EOT
retries=12
until gcloud builds list --quiet --project="${data.google_project.cluster.project_id}"
do
  if ((retries <= 0)); then
    exit 1
  fi

  retries=$((retries - 1))
  echo "Waiting for Cloud Spanner API to be enabled..."
  sleep 5
done
EOT
  }

  depends_on = [
    google_project_service.cloud_build_googleapis_com,
  ]
}

resource "google_cloudbuild_worker_pool" "privatepool" {
  name     = "privatepool"
  location = var.cluster_region
  project  = google_project_service.cloud_build_googleapis_com.project

  worker_config {
    machine_type   = "e2-standard-32"
    no_external_ip = true
  }

  depends_on = [terraform_data.wait_for_cloud_build_api]
}

resource "google_project_service_identity" "cloudbuild_sa" {
  provider = google-beta
  project  = google_project_service.cloud_build_googleapis_com.project
  service  = google_project_service.cloud_build_googleapis_com.service
}

resource "google_project_iam_member" "cloudbuild_sa_roles" {
  for_each = toset(local.cloudbuild_sa_roles)
  project  = data.google_project.cluster.name
  role     = each.key
  member   = google_project_service_identity.cloudbuild_sa.member
}

resource "terraform_data" "build_workloads_images" {
  input = {
    # Checkout a specific tag to make the build reproducible
    git_clone_command         = local.cloudbuild_git_clone_command
    cloudbuild_submit_command = local.cloudbuild_submit_command
  }

  provisioner "local-exec" {
    command     = <<EOT
${self.input.git_clone_command}
${self.input.cloudbuild_submit_command}
EOT
    interpreter = ["bash", "-o", "errexit", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    federatedcompute_tag = var.federated_learning_cross_device_example_federatedcompute_tag
    cloudbuild_sa_email  = google_project_service_identity.cloudbuild_sa.email
  }

  depends_on = [
    google_cloudbuild_worker_pool.privatepool
  ]
}
