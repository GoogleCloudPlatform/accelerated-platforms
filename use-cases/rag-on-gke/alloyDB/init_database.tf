data "google_client_config" "provider" {}

data "google_container_cluster" "my_cluster" {
  name     = var.gke_cluster_name
  location = var.gke_cluster_location
  project  = var.project_id
}

provider "kubernetes" {
  host  = "https://${data.google_container_cluster.my_cluster.endpoint}"
  token = data.google_client_config.provider.access_token
  cluster_ca_certificate = base64decode(
    data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate,
  )
}

module "alloydb-cluster" {
  source = "./build-db"
  project_id = var.project_id
  network_name = var.network_name
  alloydb_ip_range = var.alloydb_ip_range
  alloydb_ip_prefix = var.alloydb_ip_prefix
}

resource "google_service_account_iam_binding" "admin-account-iam" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/alloydb-superuser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.dba_service_account}]"
  ]
  depends_on = [
    module.alloydb-cluster
  ]
}

resource "google_service_account_iam_binding" "raguser-account-iam" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/alloydb-raguser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.rag_service_account}]"
  ]
  depends_on = [
    module.alloydb-cluster
  ]
}

resource "kubernetes_service_account" "dba_service_account" {
  metadata {
    name = var.dba_service_account
    namespace = var.k8s_namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = "alloydb-superuser@${var.project_id}.iam.gserviceaccount.com"
      "iam.gke.io/scopes-override" = "https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/alloydb.login,openid"
    }
  }
  depends_on = [
    google_service_account_iam_binding.admin-account-iam
  ]
}

resource "kubernetes_service_account" "rag_service_account" {
  metadata {
    name = var.rag_service_account
    namespace = var.k8s_namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = "alloydb-raguser@${var.project_id}.iam.gserviceaccount.com"
      "iam.gke.io/scopes-override" = "https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/alloydb.login,openid"
    }
  }
  depends_on = [
    google_service_account_iam_binding.raguser-account-iam
  ]
}

module "createdb" {
  source = "./kube-psql-job"
  project_id = var.project_id
  name = "init-test"
  gke_cluster_name = var.gke_cluster_name
  gke_cluster_location = var.gke_cluster_location
  sql_script = "select current_user;"
  environs = {}
  pghost = module.alloydb-cluster.primary_instance_ip
  pgdatabase = "postgres"
  k8s_namespace = var.k8s_namespace
  k8s_service_account = var.dba_service_account
  depends_on = [
    kubernetes_service_account.dba_service_account
  ]
}
