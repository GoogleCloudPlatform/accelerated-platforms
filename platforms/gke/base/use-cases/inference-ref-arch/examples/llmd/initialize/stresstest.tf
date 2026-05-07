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

resource "google_service_account" "llmd_user" {
  account_id   = local.stress_test_service_account_name
  description  = "Terraform-managed service account for ${local.stress_test_service_account_name}"
  display_name = "${local.stress_test_service_account_name} service account"
  project      = local.stress_test_service_account_project_id
}

resource "google_iap_web_backend_service_iam_member" "stress_test_sa_iap_https_resource_accessor" {
  depends_on = [google_iap_web_backend_service_iam_member.service_account_iap_https_resource_accessor]
  member     = google_service_account.llmd_user.member
  role       = "roles/iap.httpsResourceAccessor"
  project    = local.cluster_project_id
  web_backend_service = basename(
    one(
      [
        for backend in split(", ", data.kubernetes_resources.gateway.objects[0].metadata.annotations["networking.gke.io/backend-services"]) : backend
        if can(regex(local.gradio_backend_service_regex, backend))
      ]
    )
  )
}
