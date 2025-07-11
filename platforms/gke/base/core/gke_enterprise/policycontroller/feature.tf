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

locals {
  policy_controller_kubernetes_namespace       = "gatekeeper-system"
  policy_controller_kubernetes_service_account = "gatekeeper-admin"
  gatekeeper_wi_member                         = "${local.wi_principal_prefix}/ns/${local.policy_controller_kubernetes_namespace}/sa/${local.policy_controller_kubernetes_service_account}"
  wi_principal_prefix                          = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"

  gatekeeper_iam_roles = [
    "roles/monitoring.metricWriter"
  ]
}

resource "google_gke_hub_feature" "policycontroller" {
  provider = google-beta

  location = "global"
  name     = "policycontroller"
  project  = google_project_service.anthospolicycontroller_googleapis_com.project
}

resource "google_gke_hub_feature_membership" "cluster_policycontroller" {
  provider = google-beta

  feature    = google_gke_hub_feature.policycontroller.name
  location   = google_gke_hub_feature.policycontroller.location
  membership = data.google_container_cluster.cluster.name
  project    = google_gke_hub_feature.policycontroller.project

  policycontroller {
    policy_controller_hub_config {
      policy_content {
        template_library {
          installation = "ALL"
        }
        dynamic "bundles" {
          for_each = var.policycontroller_bundles
          content {
            bundle_name = each.value
          }
        }
      }
      audit_interval_seconds    = 60
      install_spec              = "INSTALL_SPEC_ENABLED"
      log_denies_enabled        = true
      mutation_enabled          = true
      referential_rules_enabled = true
    }
  }
}

resource "google_project_iam_member" "gatekeeper" {
  for_each = toset(local.gatekeeper_iam_roles)

  member  = local.gatekeeper_wi_member
  project = google_project_service.anthospolicycontroller_googleapis_com.project
  role    = each.value
}
