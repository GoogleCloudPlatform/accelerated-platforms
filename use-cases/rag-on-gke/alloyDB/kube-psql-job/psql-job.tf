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

resource "kubernetes_config_map" "get-token" {
  metadata {
    name = "get-token-script-${var.name}"
    namespace = var.k8s_namespace
  }
  data = {
    "get_token.pl" = file("${path.module}/scripts/get_access_token_4_psql.pl")
  }
}

resource "kubernetes_config_map" "db-prepare" {
  metadata {
    name = "db-prepare-script-${var.name}"
    namespace = var.k8s_namespace    
  }
  
  data = {
    "prepare.sql" = var.sql_script
  }
}

resource "kubernetes_job" "test-pr" {
 metadata {
   name = "job-with-wait-${var.name}"
   namespace = var.k8s_namespace   
 }
 spec {
   completions = 1
   template {
     metadata {}
     spec {
       container {
	 name = "psql"
	 env = concat(
	   [for k, v in var.environs: {
	     name = k,
	     value = v
	   }],
	   [	   
	     {
	       name = "PGDATABASE"
	       value = var.pgdatabase
	     },
	     {
	       name = "PGHOST"
	       value = var.pghost
	     },
	     {
	       name = "PGPORT"
	       value = 5432   
	     }
	   ])
         image = var.postgres_image
	 command = ["/bin/bash"]
	 args = ["-c",
	   <<-EOT
           source <(perl /pl_scripts/get_token.pl)
           export PGUSER
           export PGPASSWORD
           sleep 1000000           
	   psql -f", "/sql_scripts/prepare.sql"]
           EOT
	 ]
	 volume_mount {
	   mount_path = "/sql_scripts"
	   name = "db-prepare-script"
	 }
	 volume_mount {
	   mount_path = "/pl_scripts"
	   name = "get-token"
	 }
       }
       restart_policy = "Never"
       volume {
	 config_map = kubernetes_config_map.db-prepare.metadata.name
	 name = "db-prepare-script"
       }
       volume {
	 config_map = kubernetes_config_map.get-token.metadata.name
	 name = "get-token"
       }
     }
   }
 }
 wait_for_completion = true
 timeouts {
   create = "40s"
 }
}




