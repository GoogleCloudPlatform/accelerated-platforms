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

# resource "google_project_iam_member" "google_provided_cloudbuild" {
#   for_each = toset([
#     "roles/secretmanager.admin",
#   ])

#   member  = "serviceAccount:service-${data.google_project.default.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
#   project = data.google_project.default.project_id
#   role    = each.value
# }
