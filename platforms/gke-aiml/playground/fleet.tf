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

#
# Removing to all for multiple environments in the same project
#
# resource "google_gke_hub_feature" "configmanagement" {
#   depends_on = [
#     google_project_service.anthos_googleapis_com,
#     google_project_service.anthosconfigmanagement_googleapis_com,
#     google_project_service.compute_googleapis_com,
#     google_project_service.gkeconnect_googleapis_com,
#     google_project_service.gkehub_googleapis_com,
#     local.configsync_repository
#   ]

#   location = "global"
#   name     = "configmanagement"
#   project  = data.google_project.environment.project_id
# }

resource "null_resource" "gke_hub_feature_configmanagement" {
  depends_on = [
    google_project_service.anthos_googleapis_com,
    google_project_service.anthosconfigmanagement_googleapis_com,
    google_project_service.compute_googleapis_com,
    google_project_service.gkeconnect_googleapis_com,
    google_project_service.gkehub_googleapis_com,
    local.configsync_repository
  ]

  provisioner "local-exec" {
    command = "gcloud beta container fleet config-management enable --project ${var.environment_project_id}"
  }
}

resource "terraform_data" "wait_for_cluster_operations" {
  depends_on = [
    google_container_cluster.mlp,
  ]

  input = {
    query = jsonencode(
      {
        cluster_name   = google_container_cluster.mlp.name
        cluster_region = var.region
        project_id     = data.google_project.environment.project_id
        timeout        = "60"
      }
    )
  }

  provisioner "local-exec" {
    command     = "${path.module}/../../gke/base/scripts/container_cluster/wait_for_cluster_operations.sh <<< '${self.input.query}'"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    always_run = timestamp()
  }
}

resource "google_gke_hub_membership" "cluster" {
  depends_on = [
    google_container_cluster.mlp,
    google_project_service.gkeconnect_googleapis_com,
    google_project_service.gkehub_googleapis_com,
    terraform_data.wait_for_cluster_operations,
  ]

  membership_id = google_container_cluster.mlp.name
  project       = data.google_project.environment.project_id

  endpoint {
    gke_cluster {
      resource_link = "//container.googleapis.com/${google_container_cluster.mlp.id}"
    }
  }

  provisioner "local-exec" {
    command = "${path.module}/../../gke/base/scripts/container_cluster/wait_for_cluster_operations.sh <<< '${jsonencode({
      cluster_name   = self.membership_id
      cluster_region = regex("locations/([^/]+)/clusters", self.endpoint[0].gke_cluster[0].resource_link)[0]
      project_id     = self.project
      timeout        = "600"
    })}'"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }
}
