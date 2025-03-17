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
  gsa_build_account_id = "${local.cluster_name}-${var.fine_tuning_team_namespace}-build"
}

resource "google_service_account" "fine_tuning_build" {
  project      = data.google_project.fine_tuning.project_id
  account_id   = local.gsa_build_account_id
  display_name = "${local.gsa_build_account_id} Service Account"
  description  = "Terraform-managed service account for ${local.gsa_build_account_id}"
}
