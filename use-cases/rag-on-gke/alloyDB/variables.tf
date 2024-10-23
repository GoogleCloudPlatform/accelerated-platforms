
variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "network_name" {
  description = "The ID of the network in which to provision resources."
  type        = string
  default     = "default"
}

variable "alloydb_ip_range" {
  description = "The ip range allocated for alloydb instances"
  type        = string
  default     = "172.16.0.0"
}
variable "alloydb_ip_prefix" {
  description = "The ip prefix used for allocating ip address for alloydb instances"
  type        = number
  default     = 12
}

variable "region_central" {
  default     = "us-central1"
  description = "The region for cluster in central us"
  type        = string
}

variable "region_east" {
  default     = "us-east1"
  description = "The region for cluster in east us"
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
  
variable "environs" {
  description = "The environment variables to be transferred to psql"
  type        = map(string)
}

variable "pghost" {
  description = "The database host to connect to"
  type        = string
}

variable "pgdatabase" {
  description = "The database to connect to"
  type        = string
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
