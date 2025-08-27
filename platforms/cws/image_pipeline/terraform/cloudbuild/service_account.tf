# Copyright 2025 Aaron Rueth <aaron@rueth.io>
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

# Create the build service account
resource "google_service_account" "gccwsi_build" {
  account_id   = "gccwsi-build"
  description  = "Terraform-managed service account for gc-cloud-workstation-image build"
  display_name = "gc-cloud-workstation-image build service account"
  project      = data.google_project.cloudbuild.project_id
}

# Create the scheduler service account
resource "google_service_account" "gccwsi_sched" {
  account_id   = "gccwsi-sched"
  description  = "Terraform-managed service account for gc-cloud-workstation-image scheduler"
  display_name = "gc-cloud-workstation-image scheduler service account"
  project      = data.google_project.cloudbuild.project_id
}

# Create the Terraform service account
resource "google_service_account" "gccwsi_iac" {
  account_id   = "gccwsi-iac"
  description  = "Terraform-managed service account for gc-cloud-workstation-image IaC"
  display_name = "gc-cloud-workstation-image IaC service account"
  project      = data.google_project.cloudbuild.project_id
}
