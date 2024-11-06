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
  description = "The GCP project to find the GKE cluster"
  type        = string
}

variable "k8s_service_account" {
  description = "The k8s service account to be attached to the pod"
  type        = string
  default     = "default"
}

variable "name" {
  description = "The name of the module, to be append to each k8s resource name"
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

variable "sql_script" {
  description = "The SQL script to be run by psql"
  type        = string
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
