# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

variable "alloydb_primary_instance" {
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

variable "gke_cluster_project_id" {
  description = "The project where the GKE cluster is in. If not specified, use project_id"
  type        = string
  default     = null
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

variable "use_gke_connect_gateway" {
  description = "Whether or not using the connect gateway to access the gke cluster"
  type        = bool
  default     = false
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

variable "pretrained_model_endpoint" {
  description = "The endpoint to the pretrained model"
  type        = string
  default     = ""
}

variable "embedding_endpoint" {
  description = "The endpoint to the embedding service"
  type        = string
  default     = ""  
}

variable "template_database" {
  description = "The template database used when do CREATE DATABASE"
  type        = string
  default     = "postgres"
}

variable "skip_ml_integration" {
  description = "Skip the creation of google_ml_integraion"
  type        = bool
  default     = true
}
  
