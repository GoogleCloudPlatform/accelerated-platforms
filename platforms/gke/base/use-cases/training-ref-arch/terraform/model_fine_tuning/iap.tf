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
  mft_iap_domain = var.mft_iap_domain != null ? var.mft_iap_domain : split("@", trimspace(data.google_client_openid_userinfo.identity.email))[1]
  # TODO: Look at adding validation that the OAuth brand exists
  iap_oath_brand = "projects/${data.google_project.iap.project_id}/brands/${data.google_project.iap.number}"
}

# TODO: Look at possibly converting to google_iap_web_backend_service_iam_member, but would need the gateway to be created first.
# BACKEND_SERVICE=$(gcloud compute backend-services list --filter="name~'<backend-service>'" --format="value(name)")
resource "google_iap_web_iam_member" "domain_iap_https_resource_accessor" {
  depends_on = [
    module.kubectl_wait_for_gateway,
  ]

  project = data.google_project.iap.project_id
  member  = "domain:${local.mft_iap_domain}"
  role    = "roles/iap.httpsResourceAccessor"
}
