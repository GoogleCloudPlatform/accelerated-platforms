
variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}


variable "alloydb_region" {
  default     = "us-central1"
  description = "The region for cluster in central us"
  type        = string
}

variable "alloydb_cluster" {
  description = "The alloydb cluster name"
  type        = string
}

variable "alloydb_instance" {
  description = "The primary instance name in the alloydb cluster"
  type        = string
}

variable "dba_service_account" {
  description = "The k8s service account of alloydb superuser"
  type        = string
}

variable "rag_service_account" {
  description = "The k8s service account of alloydb rag"
  type        = string
}


variable "gke_cluster_name" {
  description = "The name of GKE cluster to deploy to"
  type        = string
}

variable "gke_cluster_location" {
  description = "The location of GKE cluster to deploy to"
  type        = string
  default     = "us-central1"
}


variable "k8s_namespace" {
  description = "The k8s namespace to deploy resourcs to"
  type        = string
  default     = "default"
}

variable "postgres_image" {
  description = "The container image of postgresql"
  type        = string
  default     = "postgres:16.4"
}

variable  "finetuned_model_endpoint" {
  description = "The endpoint to the finetuned model"
  type = string
}

variable "pretrained_model_endpoint" {
  description = "The endpoint to the pretrained model"
  type = string
}

variable "embedding_endpoint" {
  description = "The endpoint to the embedding service"
  type = string
}
