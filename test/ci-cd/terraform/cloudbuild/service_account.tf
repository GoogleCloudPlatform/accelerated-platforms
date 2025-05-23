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

# Create the scheduler service account
resource "google_service_account" "cicd_sched" {
  account_id   = "cicd-sched"
  description  = "Terraform-managed service account for CI/CD scheduler"
  display_name = "ci-cd scheduler service account"
  project      = data.google_project.build.project_id
}

resource "google_service_account" "integration" {
  project      = data.google_project.build.project_id
  account_id   = "integration"
  display_name = "integration"
  description  = "Integration service account"
}
