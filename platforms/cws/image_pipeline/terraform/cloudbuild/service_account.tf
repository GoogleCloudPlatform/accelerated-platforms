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

# Create the build service account
resource "google_service_account" "cws_image_pipeline_build" {
  account_id   = local.cloudbuild_cws_image_pipeline_build_sa_name
  description  = "Terraform-managed service account for CWS image-pipeline build"
  display_name = "image-pipeline build service account"
  project      = local.cloudbuild_cws_image_pipeline_build_sa_project_id
}

# Create the scheduler service account
resource "google_service_account" "cws_image_pipeline_sched" {
  account_id   = local.cloudbuild_cws_image_pipeline_scheduler_sa_name
  description  = "Terraform-managed service account for CWS image-pipeline scheduler"
  display_name = "image-pipeline scheduler service account"
  project      = local.cloudbuild_cws_image_pipeline_scheduler_sa_project_id
}

# Create the Terraform service account
# resource "google_service_account" "cws_image_pipeline_iac" {
#   account_id   = "${local.unique_identifier_prefix}-cws-ip-iac"
#   description  = "Terraform-managed service account for CWS image-pipeline IaC"
#   display_name = "image-pipeline IaC service account"
#   project      = data.google_project.cloudbuild.project_id
# }
