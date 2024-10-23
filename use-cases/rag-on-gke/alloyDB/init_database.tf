

resource "google_service_account_iam_binding" "admin-account-iam" {
  service_account_id = "alloydb-superuser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.dba_service_account}]"
  ]
}

resource "google_service_account_iam_binding" "raguser-account-iam" {
  service_account_id = "alloydb-raguser@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.rag_service_account}]"
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
  pghost = var.pghost
  pgdatabase = var.pgdatabase
  k8s_namespace = var.k8s_namespace
  k8s_service_account = kubernetes_service_account.dba_service_account.metadata[0].name
}
