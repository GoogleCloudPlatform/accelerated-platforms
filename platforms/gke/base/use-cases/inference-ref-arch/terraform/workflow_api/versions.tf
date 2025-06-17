terraform {
  required_version = ">= 1.5.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.38.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.37.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "2.5.3"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/workflow-api_deploy-v1"
  }
}
