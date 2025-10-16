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
  cloudbuild_builds_creator_role_id   = "${local.unique_identifier_prefix_underscore}.cws.builds.creator.${var.platform_custom_role_unique_suffix}"
  cloudbuild_builds_creator_role_name = "projects/${local.cloudbuild_project_id}/roles/${local.cloudbuild_builds_creator_role_id}"
}

data "google_project" "cloudbuild" {
  project_id = local.cloudbuild_project_id
}
