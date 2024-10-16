terraform {
 required_providers {
   kubernetes = {
     source = "hashicorp/kubernetes"
   }
 }
}
 
provider "kubernetes" {
 config_path = "~/.kube/config"
}

resource "kubernetes_config_map" "db-prepare" {
  metadata {
    name = "db-prepare-script"
  }
  
  data = {
    "ml-integration.sql" = "${file("${path.module}/assets/ml-integration.sql")}"
  }
}

resource "kubernetes_config_map" "ml-endpoints" {
  metadata {
    name = "ml-endpoints"
  }
  data = {
    "finetune_model_ep" = "http://10.150.0.32:8000/v1/completions"
    "pretrained_model_ep" = "http://10.150.0.23:8000/v1/completions"
    "embedding_endpoint" = "http://10.150.15.227/embeddings"
  }
}

resource "kubernetes_job" "test-pr" {
 metadata {
   name = "job-with-wait"
   namespace = "default"
 }
 spec {
   completions = 1
   template {
     metadata {}
     spec {
       container {
	 name = "psql"
	 env = [
	   {
	     name = "FINETUNE_MODEL_EP"
	     value_from = {
	       config_map_key_ref = {
		 key = "finetune_model_ep"
		 name = "ml-endpoints"
	       }
	     }
	   },
	   {
	     name = "PRETRAINED_MODEL_EP"
	     value_from = {
	       config_map_key_ref = {
		 key = "pretrained_moel_ep"
		 name = "ml-endpoints"
	       }
	     }
	   },
	   {
	     name = "EMBEDDING_ENDPOINT"
	     value_from = {
	       config_map_key_ref = {
		 key = "embedding_endpoint"
		 name = "ml-endpoints"
	       }
	     }
	   },
	   {
	     name = "PGDATABASE"
	     value_from = {
	       secret_key_ref = {
		 key = "database"
		 name = "alloydb-super"
	       }
	     }
	   },
	   {
	     name = "PGHOST"
	     value_from = {
	       secret_key_ref = {
		 key = "host"
		 name = "alloydb-super"
	       }
	     }
	   },
	   {
	     name = "PGPORT"
	     value_from = {
	       secret_key_ref = {
		 key = "port"
		 name = "alloydb-super"
	       }
	     }	     
	   },
	   {
	     name = "PGUSER"
	     value_from = {
	       secret_key_ref = {
		 key = "user"
		 name = "alloydb-super"
	       }
	     }	     
	   },
	   {
	     name = "PGPASSWORD"
	     value_from = {
	       secret_key_ref = {
		 key = "password"
		 name = "alloydb-super"
	       }
	     }	     	     
	   },
	 ]
         image = "postgres:16.4"
	 command = ["psql", "-f", "/scripts/ml-integration.sql"]
	 volume_mount = [
	   {
	     mount_path = "/scripts"
	     name = "db-prepare-script"
	   }
	 ]    
       }
       restart_policy = "Never"
       volume = {
	 config_map = "db-prepare-script"
	 name = "db-prepare-script"
       }
     }
   }
 }
 wait_for_completion = true
 timeouts {
   create = "40s"
 }
}




