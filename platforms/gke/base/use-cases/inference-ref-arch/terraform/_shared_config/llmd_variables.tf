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

locals {
  gradio_cloudbuild_project_id             = var.gradio_cloudbuild_project_id != null ? var.gradio_cloudbuild_project_id : local.cloudbuild_project_id
  gradio_cloudbuild_service_account_email  = "${local.gradio_cloudbuild_service_account_name}@${local.gradio_cloudbuild_project_id}.iam.gserviceaccount.com"
  gradio_cloudbuild_service_account_id     = "projects/${local.gradio_cloudbuild_project_id}/serviceAccounts/${local.gradio_cloudbuild_service_account_email}"
  gradio_cloudbuild_service_account_name   = var.gradio_cloudbuild_service_account_name != null ? var.gradio_cloudbuild_service_account_name : local.cloudbuild_service_account_name
  gradio_cloudbuild_source_bucket_location = var.gradio_cloudbuild_source_bucket_location != null ? var.gradio_cloudbuild_source_bucket_location : local.cloudbuild_location
  gradio_cloudbuild_source_bucket_name     = var.gradio_cloudbuild_source_bucket_name != null ? var.gradio_cloudbuild_source_bucket_name : local.cloudbuild_source_bucket_name
  llmd_backend_policy_name                 = var.llmd_backend_policy_name != null ? var.llmd_backend_policy_name : "gaie-${local.llmd_release_name}"
  llmd_default_name                        = "llmd"
  llmd_endpoints_hostname                  = var.llmd_endpoints_hostname != null ? var.llmd_endpoints_hostname : "llmd.${var.llmd_kubernetes_namespace}.${local.unique_identifier_prefix}.endpoints.${local.cluster_project_id}.cloud.goog"
  llmd_endpoints_ssl_certificate_name      = "${local.unique_identifier_prefix}-${var.llmd_kubernetes_namespace}-external-gateway"
  llmd_gateway_address_name                = "${local.unique_identifier_prefix}-${local.llmd_default_name}-external-gateway-https"
  llmd_gateway_name_external               = var.llmd_gateway_name_external != null ? var.llmd_gateway_name_external : "${local.llmd_default_name}-gateway-external"
  llmd_gateway_name_internal               = var.llmd_gateway_name_internal != null ? var.llmd_gateway_name_internal : "infra-${local.llmd_release_name}-inference-gateway"
  llmd_httproute_name_external             = var.llmd_httproute_name_external != null ? var.llmd_httproute_name_external : "${local.llmd_default_name}-httproute-external"
  llmd_httproute_name_internal             = var.llmd_httproute_name_internal != null ? var.llmd_httproute_name_internal : "${local.llmd_default_name}-${local.llmd_release_name}-internal"
  llmd_iap_oath_branding_project_id        = var.llmd_iap_oath_branding_project_id != null ? var.llmd_iap_oath_branding_project_id : var.platform_default_project_id
  llmd_inferencepool_name                  = var.llmd_inferencepool_name != null ? var.llmd_inferencepool_name : "gaie-${local.llmd_release_name}"
  llmd_modelserver_sa                      = var.llmd_modelserver_sa != null ? var.llmd_modelserver_sa : "ms-${local.llmd_release_name}-${local.llmd_default_name}-modelserver-sa"
  llmd_ms_deployment_name                  = var.llmd_ms_deployment_name != null ? var.llmd_ms_deployment_name : "ms-${local.llmd_release_name}-${local.llmd_default_name}-modelservice"
  llmd_release_name                        = var.llmd_release_name != null ? var.llmd_release_name : "inference-scheduling"
  stress_test_service_account_project_id   = var.stress_test_service_account_project_id != null ? var.stress_test_service_account_project_id : var.platform_default_project_id
  stress_test_service_account_email        = "${local.stress_test_service_account_name}@${local.stress_test_service_account_project_id}.iam.gserviceaccount.com"
  stress_test_service_account_name         = "${local.unique_identifier_prefix}-${local.llmd_default_name}"
}

variable "gaie_chart" {
  default     = "oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool"
  description = "Helm chart for llmd infra"
  type        = string
}

variable "gaie_chart_version" {
  default     = "v1.2.0-rc.1"
  description = "Version of the Helm chart for llmd infra"
  type        = string
}

variable "gradio_artifact_repo_name" {
  default = "gradio"
  type    = string
}

variable "gradio_cloudbuild_project_id" {
  default     = null
  description = "Cloud Build project ID for gradio image builds."
  type        = string

}

variable "gradio_cloudbuild_service_account_name" {
  default     = null
  description = "Cloud Build service account name for gradio image builds."
  type        = string

}

variable "gradio_cloudbuild_source_bucket_location" {
  default     = null
  description = "Cloud Build source bucket location for gradio image builds."
  type        = string

}

variable "gradio_cloudbuild_source_bucket_name" {
  default     = null
  description = "Cloud Build source bucket name for gradio image builds."
  type        = string

}

variable "gradio_image_name" {
  default = "gradio"
  type    = string
}

variable "gradio_image_staging_bucket" {
  default = "gradio-image-staging"
  type    = string
}

variable "gradio_image_tag" {
  default = "0.0.1"
  type    = string
}

variable "kubernetes_version" {
  default     = "1.28.0"
  description = "The Kubernetes version to use when templating."
  type        = string
}

variable "llmd_accelerator_type" {
  default = "nvidia-l4"
  type    = string

  validation {
    condition = contains(
      [
        "nvidia-a100-80gb",
        "nvidia-h100-80gb",
        "nvidia-l4",
        "nvidia-rtx-pro",
        "nvidia-tesla-a100",
      ],
      var.llmd_accelerator_type
    )
    error_message = "'llmd_accelerator_type' value is invalid"
  }
}

variable "llmd_backend_policy_name" {
  default     = null
  description = "The name of the backend policy."
  type        = string
}

variable "llmd_endpoints_hostname" {
  default     = null
  description = "Endpoint name for external access."
  type        = string
}

variable "llmd_gateway_name_external" {
  default     = null
  description = "Name of the external gateway for gradio access."
  type        = string
}

variable "llmd_gateway_name_internal" {
  default     = null
  description = "Name of the internal gateway."
  type        = string
}

variable "llmd_httproute_name_external" {
  default     = null
  description = "Name of the external http route for gradio access."
  type        = string
}

variable "llmd_httproute_name_internal" {
  default     = null
  description = "Name of the internal http route."
  type        = string
}

variable "llmd_huggingface_spc" {
  default     = "huggingface-read-token"
  description = "Name of the service provider class to store the huggingface secret"
  type        = string
}

variable "llmd_iap_domain" {
  default     = null
  description = "IAP domain for the app"
  type        = string
}

variable "llmd_iap_oath_branding_project_id" {
  default     = null
  description = "IAP brand for the Google Cloud project id"
  type        = string
}

variable "llmd_inferencepool_name" {
  default     = null
  description = "Name of the InferencePool that the LB will point to."
  type        = string
}

variable "llmd_kubernetes_namespace" {
  default     = "llmd"
  description = "The Kubernetes namespace to deploy the manifests to."
  type        = string
}

variable "llmd_model_name" {
  default     = "Qwen/Qwen3-0.6B"
  description = "model to server"
  type        = string
}

variable "llmd_modelserver_sa" {
  default     = null
  description = "Service Account name for running model server"
  type        = string
}

variable "llmd_ms_cuda_image" {
  default     = "ghcr.io/llm-d/llm-d-cuda:v0.3.1"
  description = "CUDA image for model server deployment"
  type        = string
}

variable "llmd_ms_deployment_name" {
  default     = null
  description = "Model server deployment name"
  type        = string
}

variable "llmd_ms_proxy_image" {
  default     = "ghcr.io/llm-d/llm-d-routing-sidecar:v0.4.0-rc.1"
  description = "image of the routing proxy in model server"
  type        = string
}

variable "llmd_release_name" {
  default     = null
  description = "Unique release name for the helm chart deployment."
  type        = any
  #  default = "inference-scheduling"
}

variable "stress_test_service_account_project_id" {
  default     = null
  description = "Project id where the service account for stress test will be created."
  type        = string
}

variable "skip_tests" {
  default     = false
  description = "If set, tests will not be rendered. By default, tests are rendered."
  type        = bool
}

variable "validate_manifests" {
  default     = false
  description = "Validate the manifests against the Kubernetes cluster."
  type        = bool
}


# variable "kubernetes_namespace_create" {
#   description = "Create the Kubernetes namespace."
#   type        = bool
# }

# variable "llmd_infra_repo" {
#   description = "Helm repo for llmd infra"
#   type        = string
# }

# variable "llmd_infra_chart" {
#   description = "Helm chart for llmd infra"
#   type        = string
# }

# variable "llmd_infra_chart_version" {
#   description = "Version of the Helm chart for llmd infra"
#   type        = string
# }
