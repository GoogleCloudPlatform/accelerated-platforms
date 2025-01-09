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
  # Minimal roles for nodepool SA https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster#use_least_privilege_sa
  cluster_sa_roles = [
    "roles/artifactregistry.reader",
    "roles/autoscaling.metricsWriter",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/stackdriver.resourceMetadata.writer",
  ]
}

# Create dedicated service account for the cluster nodes
resource "google_service_account" "cluster" {
  for_each = toset(var.cluster_node_pool_default_service_account_id == null ? ["created"] : [])

  account_id   = local.cluster_node_pool_service_account_id
  description  = "Terraform-managed service account for cluster ${local.cluster_name}"
  display_name = "${local.cluster_name} default Service Account"
  project      = data.google_project.cluster.project_id
}

# Bind minimum role list to the service account
resource "google_project_iam_member" "cluster_sa" {
  for_each = toset(var.cluster_node_pool_default_service_account_id == null ? local.cluster_sa_roles : [])

  member  = google_service_account.cluster["created"].member
  project = data.google_project.cluster.project_id
  role    = each.value
}

data "google_service_account" "cluster" {
  depends_on = [google_service_account.cluster]

  account_id = local.cluster_node_pool_service_account_id
  project    = local.cluster_node_pool_service_account_project_id
}
