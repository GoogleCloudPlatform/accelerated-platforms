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
  cloudbuild_submit_command    = "while ! gcloud builds submit --substitutions=_PROJECT_ID=\"${local.cloudbuild_project_id},_REGISTRY=${local.cloudbuild_location}-docker.pkg.dev/${local.cloudbuild_project_id}/${local.federated_learning_repository_id}\" --region ${local.cloudbuild_location} --service-account=\"${local.cloudbuild_service_account_id}\" --gcs-source-staging-dir=\"${local.cloudbuild_source_bucket_name}/source\" --gcs-log-dir=\"${local.cloudbuild_source_bucket_name}/logs\" --config=cloudbuild.yaml; do echo \"Building workloads images\"; sleep 5; done"
  cloudbuild_git_clone_command = "if [ -d odp-federatedcompute ]; then rm -rf odp-federatedcompute; fi; git clone --recurse-submodules https://github.com/privacysandbox/odp-federatedcompute --branch=${var.federated_learning_cross_device_example_federatedcompute_tag}; cd odp-federatedcompute; sed -i '30s/^#//;31s/^#//' cloudbuild.yaml"
  cloudbuild_sa_roles = [
    "roles/cloudbuild.builds.builder",
    "roles/cloudbuild.workerPoolUser",
    "roles/storage.objectUser",
    "roles/logging.logWriter",
    "roles/artifactregistry.writer"
  ]
}

resource "google_cloudbuild_worker_pool" "privatepool" {
  # Needed for cloudbuild.yaml
  name     = "odp-federatedcompute-privatepool"
  location = local.cloudbuild_location
  project  = google_project_service.cloud_build_googleapis_com.project

  worker_config {
    machine_type = "e2-standard-32"
    # Public IP for downloading from Internet
    no_external_ip = false
    disk_size_gb   = 100
  }
}

resource "google_project_iam_member" "cloudbuild_sa_roles" {
  for_each = toset(local.cloudbuild_sa_roles)
  project  = data.google_project.cluster.name
  role     = each.key
  member   = google_service_account.cloudbuild_sa.member
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
    cloudbuild_sa_email  = local.cloudbuild_service_account_email
  }

  depends_on = [
    google_cloudbuild_worker_pool.privatepool
  ]
}
