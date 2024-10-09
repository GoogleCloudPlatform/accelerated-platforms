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

resource "google_logging_project_bucket_config" "default" {
  bucket_id        = "_Default"
  enable_analytics = true
  location         = "global"
  project          = data.google_project.environment.project_id
  retention_days   = 30
}

# b/286785537
# https://github.com/hashicorp/terraform-provider-google/issues/14588
# resource "google_logging_project_bucket_config" "required" {
#   bucket_id        = "_Required"
#   description      = "Audit bucket"
#   enable_analytics = true
#   location         = "global"
#   locked           = true
#   project          = data.google_project.environment.project_id
#   retention_days   = 400
# }
resource "null_resource" "google_logging_project_bucket__required_enable_log_analytics" {
  provisioner "local-exec" {
    command = <<CURL
      curl -X POST --location "https://logging.googleapis.com/v2/projects/${data.google_project.environment.project_id}/locations/global/buckets/_Required:updateAsync?updateMask=analyticsEnabled" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${data.google_client_config.default.access_token}" \
        -d "{\"analyticsEnabled\": true}"
    CURL
  }
}
