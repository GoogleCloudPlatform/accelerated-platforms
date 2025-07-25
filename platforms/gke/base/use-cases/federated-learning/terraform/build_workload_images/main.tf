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
  cloudbuild_submit_command    = "gcloud builds submit --substitutions=_PROJECT_ID=\"${local.cloudbuild_project_id},_REGISTRY=${local.cloudbuild_location}-docker.pkg.dev/${local.cloudbuild_project_id}/${local.federated_learning_repository_id}\" --region ${local.cloudbuild_location} --service-account=\"${local.cloudbuild_service_account_id}\" --gcs-source-staging-dir=\"gs://${local.cloudbuild_source_bucket_name}/source\" --gcs-log-dir=\"gs://${local.cloudbuild_source_bucket_name}/logs\" --project=\"${local.cloudbuild_project_id}\" --config=cloudbuild.yaml"
  cloudbuild_git_clone_command = "if [ -d odp-federatedcompute ]; then rm -rf odp-federatedcompute; fi; git clone --recurse-submodules https://github.com/privacysandbox/odp-federatedcompute --branch=${var.federated_learning_cross_device_example_federatedcompute_tag}; cd odp-federatedcompute; sed -i '30s/^#//;31s/^#//' cloudbuild.yaml"
}

resource "google_cloudbuild_worker_pool" "privatepool" {
  # Needed for cloudbuild.yaml
  name     = "odp-federatedcompute-privatepool"
  location = local.cloudbuild_location
  project  = local.cloudbuild_project_id

  worker_config {
    machine_type = "e2-standard-32"
    # Public IP for downloading from Internet
    no_external_ip = false
    disk_size_gb   = 100
  }
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
