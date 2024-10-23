
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
	 dynamic "env" {
	   for_each = concat(
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
	   content {
	     name = env.value["name"]
	     value = env.value["value"]
	   }
	 }
         image = var.postgres_image
	 command = ["/bin/bash"]
	 args = ["-c",
	   <<-EOT
           source <(perl /pl_scripts/get_token.pl)
           export PGUSER
           export PGPASSWORD
	   psql -f /sql_scripts/prepare.sql
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
       service_account_name = var.k8s_service_account
       node_selector = {
	 "iam.gke.io/gke-metadata-server-enabled": "true"
       }
       restart_policy = "Never"
       volume {
	 config_map {
	   name= kubernetes_config_map.db-prepare.metadata[0].name
	 }
	 name = "db-prepare-script"
       }
       volume {
	 config_map {
	   name = kubernetes_config_map.get-token.metadata[0].name
	 }
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




