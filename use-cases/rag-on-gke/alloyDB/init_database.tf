module "createdb" {
  source = "./kube-psql-job"
  project_id = var.project_id
  name = "init-test"
  gke_cluster_name = "gpu-ml"
  gke_cluster_location = "asia-southeast1-a"
  sql_script = "select current_user;"
  environs = {}
  pghost = "127.0.0.1"
  pgdatabase = "postgres"
}
