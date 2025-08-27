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
  cloudbuild_trigger_url_prefix = "https://cloudbuild.googleapis.com/v1/projects/${data.google_project.cloudbuild.project_id}/locations/${local.cloudbuild_location}/triggers"
}

resource "google_cloud_scheduler_job" "cws_image_code_oss_daily" {
  name      = "${local.unique_identifier_prefix_underscore}-cws-image-code-oss-schedule"
  project   = data.google_project.cloudbuild.project_id
  region    = local.cloudbuild_location
  schedule  = "0 0 * * *"
  time_zone = "Etc/UTC"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.cws_image_code_oss.trigger_id}:run"

    oauth_token {
      service_account_email = data.google_service_account.cws_image_pipeline_sched.email
    }
  }
}
