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

data "external" "alloydb-primary-instance-ip" {
  program = ["gcloud",
    "--project=${var.project_id}",
    "--format=json(ipAddress)",    
    "alloydb",
    "instances",
    "describe",
    var.alloydb_instance,
    "--cluster=${var.alloydb_cluster}",
    "--region=${var.alloydb_region}"]
}


module "database-config" {
  source = "./kube-configmap"
  name = "alloydb-config"
  configdata = {
    pghost = data.external.alloydb-primary-instance-ip.result.ipAddress
    pgdatabase = "ragdb"
  }
  k8s_namespace = var.k8s_namespace
}
