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

locals {
  ate_bucket_location            = var.ate_bucket_location != null ? var.ate_bucket_location : local.cluster_region
  ate_bucket_name                = var.ate_bucket_name != null ? var.ate_bucket_name : "${local.unique_identifier_prefix}-ate-${local.ate_bucket_project_id}"
  ate_bucket_project_id          = var.ate_bucket_project_id != null ? var.ate_bucket_project_id : var.platform_default_project_id
  ate_cloudsql_instance_name     = var.ate_cloudsql_instance_name != null ? var.ate_cloudsql_instance_name : "${local.unique_identifier_prefix}-ate-pg"
  ate_cloudsql_project_id        = var.ate_cloudsql_project_id != null ? var.ate_cloudsql_project_id : var.platform_default_project_id
  ate_cloudsql_region            = var.ate_cloudsql_region != null ? var.ate_cloudsql_region : local.cluster_region
  ate_kubernetes_namespace       = var.ate_kubernetes_namespace != null ? var.ate_kubernetes_namespace : "ate-system"
  ate_service_account_email      = "${local.ate_service_account_name}@${local.ate_service_account_project_id}.iam.gserviceaccount.com"
  ate_service_account_name       = var.ate_service_account_name != null ? var.ate_service_account_name : "${local.unique_identifier_prefix}-ate-api"
  ate_service_account_project_id = var.ate_service_account_project_id != null ? var.ate_service_account_project_id : var.platform_default_project_id

  manifests_directory_root = "${path.module}/../../../kubernetes/manifests"
}

variable "agent_sandbox_version" {
  default     = "0.4.6"
  description = "Version of Agent Sandbox (https://github.com/kubernetes-sigs/agent-sandbox) to install."
  type        = string
}

variable "ate_bucket_location" {
  default     = null
  description = "The location of the Agent Substrate Cloud Storage bucket."
  nullable    = true
  type        = string
}

variable "ate_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store Agent Substrate snapshots."
  nullable    = true
  type        = string
}

variable "ate_bucket_project_id" {
  default     = null
  description = "The project ID for the Agent Substrate Cloud Storage bucket."
  nullable    = true
  type        = string
}

variable "ate_cloudsql_edition" {
  default     = "ENTERPRISE"
  description = "The edition of the Cloud SQL for PostgreSQL instance for Agent Substrate."
  type        = string
}

variable "ate_cloudsql_instance_name" {
  default     = null
  description = "The name of the Cloud SQL for PostgreSQL instance for Agent Substrate."
  nullable    = true
  type        = string
}

variable "ate_cloudsql_project_id" {
  default     = null
  description = "The project ID of the Cloud SQL for PostgreSQL instance for Agent Substrate."
  nullable    = true
  type        = string
}

variable "ate_cloudsql_region" {
  default     = null
  description = "The region of the Cloud SQL for PostgreSQL instance for Agent Substrate."
  nullable    = true
  type        = string
}

variable "ate_cloudsql_tier" {
  default     = "db-custom-2-8192"
  description = "The machine tier of the Cloud SQL for PostgreSQL instance for Agent Substrate."
  type        = string
}

variable "ate_image_repository" {
  default     = "us-docker.pkg.dev/gke-substrate-release/substrate"
  description = "The container image repository for Agent Substrate."
  type        = string
}

variable "ate_kubernetes_namespace" {
  default     = "ate-system"
  description = "The Kubernetes namespace where Agent Substrate will be deployed."
  nullable    = true
  type        = string
}

variable "ate_service_account_name" {
  default     = null
  description = "The name of the Google Service Account for Agent Substrate."
  nullable    = true
  type        = string
}

variable "ate_service_account_project_id" {
  default     = null
  description = "The project ID of the Agent Substrate Google Service Account."
  nullable    = true
  type        = string
}

variable "ate_version" {
  default     = "v0.5.0-gke.0"
  description = "Version of Agent Substrate (https://github.com/agent-substrate/substrate) to install."
  type        = string
}

variable "custom_metrics_adapter_version" {
  default     = "0.16.7"
  description = "Version of Custom Metrics Adapter (https://github.com/GoogleCloudPlatform/k8s-stackdriver) to install."
  type        = string
}

variable "inference_gateway_kubernetes_namespace" {
  default     = "gke-gateway"
  description = "The Kubernetes namespace where inference gateway resources will be deployed."
  type        = string
}

variable "inference_gateway_version" {
  default     = "1.5.0"
  description = "Version of Gateway API Inference Extension (https://github.com/kubernetes-sigs/gateway-api-inference-extension) to install."
  type        = string
}

variable "jobset_version" {
  default     = "0.12.0"
  description = "Version of JobSet (https://github.com/kubernetes-sigs/jobset/) to install."
  type        = string
}

variable "kuberay_version" {
  default     = "1.6.1"
  description = "Version of KubeRay (https://github.com/ray-project/kuberay) to install."
  type        = string
}

variable "kueue_version" {
  default     = "0.17.2"
  description = "Version of Kueue (https://github.com/kubernetes-sigs/kueue) to install."
  type        = string
}

variable "lws_version" {
  default     = "0.8.0"
  description = "Version of LeaderWorkerSet (LWS) (https://github.com/kubernetes-sigs/lws/) to install."
  type        = string
}

variable "pathways_version" {
  default     = "0.1.4"
  description = "Version of Pathways (https://github.com/google/pathways-job) to install."
  type        = string
}

variable "mlflow_version" {
  default     = "3.13.0"
  description = "Version of MLflow (https://github.com/mlflow/mlflow) to install."
  type        = string
}

variable "mlflow_kubernetes_namespace" {
  default     = null
  description = "The Kubernetes namespace where MLflow tracking will be deployed."
  type        = string
}

variable "mlflow_kubernetes_service_account_name" {
  default     = null
  description = "The Kubernetes ServiceAccount name for MLflow."
  type        = string
}

variable "mlflow_service_account_name" {
  default     = null
  description = "The name of the Google Service Account for MLflow."
  type        = string
}

variable "mlflow_service_account_project_id" {
  default     = null
  description = "The project ID of the MLflow Google Service Account."
  type        = string
}

variable "mlflow_bucket_name" {
  default     = null
  description = "The name of the Cloud Storage bucket used to store MLflow artifacts."
  type        = string
}

variable "mlflow_bucket_project_id" {
  default     = null
  description = "The project ID for the MLflow Cloud Storage bucket."
  type        = string
}

variable "mlflow_bucket_location" {
  default     = null
  description = "The location of the MLflow Cloud Storage bucket."
  type        = string
}
