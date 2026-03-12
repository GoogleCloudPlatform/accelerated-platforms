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

resource "google_artifact_registry_repository" "ci_cd" {
  description   = "CWS CI/CD images"
  format        = "DOCKER"
  location      = local.cloudbuild_location
  project       = data.google_project.cloudbuild.project_id
  repository_id = local.cloudbuild_cws_ci_cd_registry_name

  cleanup_policies {
    action = "DELETE"
    id     = "Delete untagged images"

    condition {
      tag_state = "UNTAGGED"
    }
  }
}

resource "google_artifact_registry_repository" "cloud_workstations_images" {
  description   = "CWS images"
  format        = "DOCKER"
  location      = local.cloudbuild_location
  project       = data.google_project.cloudbuild.project_id
  repository_id = local.cloudbuild_cws_image_registry_name

  cleanup_policies {
    action = "DELETE"
    id     = "Delete untagged images"

    condition {
      tag_state = "UNTAGGED"
    }
  }

  cleanup_policies {
    action = "KEEP"
    id     = "Keep 7 most recent versions"

    most_recent_versions {
      keep_count = 7
    }
  }
}

# With the Google Terraform provider, Artifact Registry repositories are not supported as custom remote repository URI.
# resource "google_artifact_registry_repository" "cloud_workstations_images_upstream" {
#   description   = "Upstream CWS image remote repository"
#   format        = "docker"
#   location      = local.cloudbuild_location
#   mode          = "REMOTE_REPOSITORY"
#   project       = data.google_project.cloudbuild.project_id
#   repository_id = local.cloudbuild_cws_image_registry_upstream_name

#   remote_repository_config {
#     docker_repository {
#       custom_repository {
#         uri = "https://${local.cloudbuild_location}-docker.pkg.dev/cloud-workstations-images/predefined"
#       }
#     }
#   }
# }

resource "terraform_data" "cloud_workstations_images_upstream" {
  input = {
    registry_name = local.cloudbuild_cws_image_registry_upstream_name
    project_id    = data.google_project.cloudbuild.project_id
    location      = local.cloudbuild_location
  }

  provisioner "local-exec" {
    command     = <<EOT
gcloud artifacts repositories create ${self.input.registry_name} \
--description="CWS upstream remote repository" \
--labels="goog-terraform-provisioned=true" \
--location="${self.input.location}" \
--mode="remote-repository" \
--project="${self.input.project_id}" \
--remote-docker-repo="https://${self.input.location}-docker.pkg.dev/cloud-workstations-images/predefined" \
--repository-format="docker"

EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = <<EOT
gcloud artifacts repositories delete ${self.input.registry_name} \
--location="${self.input.location}" \
--project="${self.input.project_id}" \
--quiet
EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }
}
