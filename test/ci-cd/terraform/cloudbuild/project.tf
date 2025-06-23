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

locals {
  cloudbuild_builds_creator_role_id   = "cloudbuild.builds.creator"
  cloudbuild_builds_creator_role_name = "projects/${data.google_project.build.project_id}/roles/${local.cloudbuild_builds_creator_role_id}"
}

data "google_project" "build" {
  project_id = var.build_project_id
}

resource "google_project_iam_custom_role" "cloudbuild_builds_creator" {
  description = "Grants permissions to create Cloud Builds"
  permissions = ["cloudbuild.builds.create"]
  project     = data.google_project.build.project_id
  role_id     = local.cloudbuild_builds_creator_role_id
  title       = "Cloud Build Builds Creator"
}

# Grant IAM permissions to the CI/CD scheduler service account
resource "google_project_iam_member" "cicd_sched" {
  for_each = toset(
    [
      local.cloudbuild_builds_creator_role_name,
      "roles/iam.serviceAccountUser",
    ]
  )

  member  = google_service_account.cicd_sched.member
  project = data.google_project.build.project_id
  role    = each.value
}
