# Copyright 2025 Google LLC
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

# Configuration dependencies
# - shared_config/platform_variables.tf

locals {
  mft_ar_repository_id  = "${local.unique_identifier_prefix}-fine-tuning"
  mft_ar_repository_url = "${local.mft_region}-docker.pkg.dev/${local.mft_project_id}/${local.mft_ar_repository_id}"

  mft_bucket_cloudbuild_name = "${local.unique_identifier_prefix}-cloudbuild-${local.mft_project_id}"
  mft_bucket_model_name      = "${local.unique_identifier_prefix}-model-${local.mft_project_id}"
  mft_data_bucket_name       = "${local.unique_identifier_prefix}-data-${local.mft_project_id}"

  mft_data_preparation_image_url            = "${local.mft_ar_repository_url}/data-preparation:1.0.0"
  mft_data_preparation_service_account_name = local.mft_kubernetes_service_accounts["data-preparation"].service_account_name

  mft_data_processing_image_url            = "${local.mft_ar_repository_url}/data-processing:1.0.0"
  mft_data_processing_service_account_name = local.mft_kubernetes_service_accounts["data-processing"].service_account_name

  mft_endpoints_hostname_suffix = "endpoints.${local.cluster_project_id}.cloud.goog"

  mft_endpoints = {
    gradio = {
      host         = "gradio.${local.mft_kubernetes_namespace}.${local.unique_identifier_prefix}.${local.mft_endpoints_hostname_suffix}"
      port         = 8080
      service_name = "gradio-svc"
    },
    locust = {
      host         = "locust.${local.mft_kubernetes_namespace}.${local.unique_identifier_prefix}.${local.mft_endpoints_hostname_suffix}"
      port         = 8089
      service_name = "locust-master-web-svc"
    },
    mlflow-tracking = {
      host         = "mlflow-tracking.${local.mft_kubernetes_namespace}.${local.unique_identifier_prefix}.${local.mft_endpoints_hostname_suffix}"
      port         = 5000
      service_name = "mlflow-tracking-svc"
    },
    ray-dashboard = {
      host         = "ray-dashboard.${local.mft_kubernetes_namespace}.${local.unique_identifier_prefix}.${local.mft_endpoints_hostname_suffix}"
      port         = 8265
      service_name = "ray-cluster-kuberay-head-svc"
    }
  }

  mft_fine_tuning_image_url            = "${local.mft_ar_repository_url}/fine-tuning:1.0.0"
  mft_fine_tuning_service_account_name = local.mft_kubernetes_service_accounts["fine-tuning"].service_account_name

  mft_kubernetes_namespace = var.mft_kubernetes_namespace != null ? var.mft_kubernetes_namespace : "${local.unique_identifier_prefix}-mft"

  mft_model_evaluation_image_url            = "${local.mft_ar_repository_url}/model-evaluation:1.0.0"
  mft_model_evaluation_service_account_name = local.mft_kubernetes_service_accounts["model-evaluation"].service_account_name

  mft_project_id = var.mft_project_id != null ? var.mft_project_id : var.platform_default_project_id
  mft_region     = var.mft_region != null ? var.mft_region : var.platform_default_region

  mft_iap_project_id = var.mft_iap_project_id != null ? var.mft_iap_project_id : var.platform_default_project_id

  mft_kubernetes_service_accounts = {
    batch-inference = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-batch-inference"
    }
    data-preparation = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-data-preparation"
    }
    data-processing = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-data-processing"
    }
    fine-tuning = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-fine-tuning"
    }
    # TODO: This should be moved to the feature when it is created.
    mlflow = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-mlflow"
    }
    model-evaluation = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-model-evaluation"
    }
    model-ops = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-model-ops"
    }
    model-serve = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-model-serve"
    }
    ray-head = {
      # automount_service_account_token is required for autoscaler to work
      automount_service_account_token = true
      service_account_name            = "${local.unique_identifier_prefix}-ray-head"
    }
    ray-worker = {
      automount_service_account_token = false
      service_account_name            = "${local.unique_identifier_prefix}-ray-worker"
    }
  }
}

variable "mft_kubernetes_namespace" {
  default     = null
  description = "The Kubernetes namespace to use for fine-tuning workloads."
  type        = string
}

variable "mft_project_id" {
  default     = null
  description = "The Google Cloud project where the fine-tuning resources will be created."
  type        = string
}

variable "mft_region" {
  default     = null
  description = "The Google Cloud region where the fine-tuning resources will be created."
  type        = string
}

variable "mft_iap_domain" {
  default     = null
  description = "Allowed domain for IAP. An internal user type audience is to limited to authorization requests for members of the organization. For more information see https://support.google.com/cloud/answer/15549945"
  type        = string
}

variable "mft_iap_project_id" {
  default     = null
  description = "Project ID of IAP brand."
  type        = string
}
