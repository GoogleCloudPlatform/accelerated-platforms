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
  gke_project_id = var.gke_cluster_project_id ? var.gke_cluster_project_id : var.project_id
  gke_url = (var.use_gke_connect_gateway ?
    join("",
      [
        "https://connectgateway.googleapis.com/v1/projects/",
        data.google_project.environment.number,
        "/locations/global/gkeMemberships/",
        data.google_container_cluster.my_cluster.name
  ]) : "https://${data.google_container_cluster.my_cluster.endpoint}")
}

data "google_client_config" "provider" {}

data "google_container_cluster" "my_cluster" {
  name     = var.gke_cluster_name
  location = var.gke_cluster_location
  project  = local.gke_project_id
}

data "google_project" "environment" {
  project_id = local.gke_project_id
}

provider "kubernetes" {
  host  = local.gke_url
  token = data.google_client_config.provider.access_token
  cluster_ca_certificate = base64decode(
    data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate,
  )
}

data "external" "alloydb_primary_instance-ip" {
  program = ["gcloud",
    "--project=${var.project_id}",
    "--format=json(ipAddress)",
    "alloydb",
    "instances",
    "describe",
    var.alloydb_primary_instance,
    "--cluster=${var.alloydb_cluster}",
  "--region=${var.alloydb_region}"]
}

module "database_config" {
  source = "./kube-configmap"
  name   = "alloydb-config"
  configdata = {
    pghost     = data.external.alloydb_primary_instance_ip.result.ipAddress
    pgdatabase = "ragdb"
  }
  k8s_namespace = var.k8s_namespace
}
