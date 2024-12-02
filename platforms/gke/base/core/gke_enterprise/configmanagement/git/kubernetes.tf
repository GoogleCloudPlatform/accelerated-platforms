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
  cluster_connect_gateway_host_url = "https://connectgateway.googleapis.com/v1/projects/${data.google_project.cluster.number}/locations/global/gkeMemberships/${local.cluster_name}"
  cluster_host_url                 = "" # TODO: Find best way to get this value for regular clusters or with DNS endpoints
  cluster_kubernetes_host_url      = var.cluster_use_connect_gateway ? local.cluster_connect_gateway_host_url : local.cluster_host_url
}

data "google_client_config" "default" {}

provider "kubernetes" {
  host  = local.cluster_kubernetes_host_url
  token = data.google_client_config.default.access_token
}

data "kubernetes_namespace" "system" {
  depends_on = [google_gke_hub_feature_membership.cluster_configmanagement]

  metadata {
    name = local.config_management_kubernetes_namespace
  }
}

resource "kubernetes_secret_v1" "git_creds" {
  data = jsondecode(data.google_secret_manager_secret_version.git_creds.secret_data)

  metadata {
    name      = "git-creds"
    namespace = data.kubernetes_namespace.system.metadata[0].name
  }
}
