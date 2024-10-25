
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
