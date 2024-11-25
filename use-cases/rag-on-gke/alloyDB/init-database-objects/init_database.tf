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

data "external" "alloydb_primary_instance_ip" {
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

resource "google_service_account_iam_binding" "admin_account_iam" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/alloydb-superuser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.dba_service_account}]"
  ]
}

resource "google_service_account_iam_binding" "raguser_account_iam" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/alloydb-raguser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.rag_service_account}]"
  ]
}

resource "kubernetes_service_account" "dba_service_account" {
  metadata {
    name      = var.dba_service_account
    namespace = var.k8s_namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = "alloydb-superuser@${var.project_id}.iam.gserviceaccount.com"
      "iam.gke.io/scopes-override"     = "https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/alloydb.login,openid"
    }
  }
  depends_on = [
    google_service_account_iam_binding.admin_account_iam
  ]
}

resource "kubernetes_service_account" "rag_service_account" {
  metadata {
    name      = var.rag_service_account
    namespace = var.k8s_namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = "alloydb-raguser@${var.project_id}.iam.gserviceaccount.com"
      "iam.gke.io/scopes-override"     = "https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/alloydb.login,openid"
    }
  }
  depends_on = [
    google_service_account_iam_binding.raguser_account_iam
  ]
}

module "createdb" {
  source               = "./kube-psql-job"
  project_id           = var.project_id
  name                 = "init-test"
  gke_cluster_name     = var.gke_cluster_name
  gke_cluster_location = var.gke_cluster_location
  sql_script           = <<-EOT
  GRANT "alloydb-raguser@${var.project_id}.iam" TO "alloydb-superuser@${var.project_id}.iam";
  CREATE DATABASE ragdb TEMPLATE ${var.template_database};
  ALTER DATABASE ragdb OWNER TO "alloydb-raguser@${var.project_id}.iam";
EOT
  environs             = {}
  pghost               = data.external.alloydb-primary-instance-ip.result.ipAddress
  pgdatabase           = "postgres"
  k8s_namespace        = var.k8s_namespace
  k8s_service_account  = var.dba_service_account
  depends_on = [
    kubernetes_service_account.dba_service_account
  ]
}

module "create_extension_pgvector" {
  source               = "./kube-psql-job"
  project_id           = var.project_id
  name                 = "init-extension-pgvector"
  gke_cluster_name     = var.gke_cluster_name
  gke_cluster_location = var.gke_cluster_location
  sql_script           = <<-EOT
  CREATE EXTENSION IF NOT EXISTS vector;
EOT
  environs             = {}
  pghost               = data.external.alloydb_primary_instance_ip.result.ipAddress
  pgdatabase           = "ragdb"
  k8s_namespace        = var.k8s_namespace
  k8s_service_account  = var.dba_service_account
  depends_on = [
    kubernetes_service_account.dba_service_account,
    module.createdb
  ]
}

module "create_extension_ml_integration" {
  count = 0 if var.skip_ml_integration else 1
  source               = "./kube-psql-job"
  project_id           = var.project_id
  name                 = "init-extension-ml-integration"
  gke_cluster_name     = var.gke_cluster_name
  gke_cluster_location = var.gke_cluster_location
  sql_script           = <<-EOT
  CREATE EXTENSION IF NOT EXISTS google_ml_integration VERSION '1.3';
  GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA google_ml
    TO "alloydb-raguser@${var.project_id}.iam";
  GRANT EXECUTE
    ON ALL FUNCTIONS IN SCHEMA google_ml
    TO "alloydb-raguser@${var.project_id}.iam";
  GRANT ALL
    ON SCHEMA google_ml
    TO "alloydb-raguser@${var.project_id}.iam";
  GRANT ALL
    ON ALL TABLES IN SCHEMA public
    TO "alloydb-raguser@${var.project_id}.iam";
  GRANT ALL
    ON ALL FUNCTIONS IN SCHEMA public
    TO "alloydb-raguser@${var.project_id}.iam";
  GRANT ALL ON SCHEMA public
    TO "alloydb-raguser@${var.project_id}.iam";
EOT
  environs             = {}
  pghost               = data.external.alloydb_primary_instance_ip.result.ipAddress
  pgdatabase           = "ragdb"
  k8s_namespace        = var.k8s_namespace
  k8s_service_account  = var.dba_service_account
  depends_on = [
    kubernetes_service_account.dba_service_account,
    module.createdb
  ]
}

module "create_in_db_objects" {
  count = 0 if var.skip_ml_integration else 1
  source               = "./kube-psql-job"
  project_id           = var.project_id
  name                 = "create-in-db-objs"
  gke_cluster_name     = var.gke_cluster_name
  gke_cluster_location = var.gke_cluster_location
  sql_script           = file("${path.module}/assets/ml-integration.sql")
  environs = {
    "PRETRAINED_MODEL_EP" = var.pretrained_model_endpoint
    "EMBEDDING_ENDPOINT"  = var.embedding_endpoint
  }
  pghost              = data.external.alloydb_primary_instance_ip.result.ipAddress
  pgdatabase          = "ragdb"
  k8s_namespace       = var.k8s_namespace
  k8s_service_account = var.rag_service_account
  depends_on = [
    kubernetes_service_account.rag_service_account,
    module.create_extension
  ]
}
