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

#
# Configuration dependencies
# - shared_config/platform_variables.tf
#

locals {
  cluster_credentials_command_private = "gcloud container clusters get-credentials ${local.cluster_name} --internal-ip --location ${var.region} --project ${var.cluster_project_id}"
  cluster_credentials_command_public  = "gcloud container clusters get-credentials ${local.cluster_name} --location ${var.region} --project ${var.cluster_project_id}"
  cluster_credentials_command_gke     = var.enable_private_endpoint ? local.cluster_credentials_command_private : local.cluster_credentials_command_public
  cluster_credentials_command_gkee    = "gcloud container fleet memberships get-credentials ${local.cluster_name} --project ${var.cluster_project_id}"
  cluster_credentials_command         = var.gke_enterprise_enable ? local.cluster_credentials_command_gkee : local.cluster_credentials_command_gke
  cluster_name                        = local.unique_identifier_prefix

  kubeconfig_directory = abspath("${path.module}/../kubeconfig")
  kubeconfig_file      = abspath("${local.kubeconfig_directory}/${var.cluster_project_id}-${local.unique_identifier_prefix}")
}

variable "cluster_project_id" {
  description = "The GCP project where the cluster resources will be created"
  type        = string

  validation {
    condition     = var.cluster_project_id != ""
    error_message = "'cluster_project_id' was not set, please set the value in the mlp.auto.tfvars file"
  }
}

variable "enable_private_endpoint" {
  default     = true
  description = "When true, the cluster's private endpoint is used as the cluster endpoint and access through the public endpoint is disabled. When false, either endpoint can be used. This field only applies to private clusters, when enable_private_nodes is true."
  type        = bool
}

variable "gke_enterprise_enable" {
  default     = true
  description = "Enable GKE Enterprise"
  type        = bool
}

variable "gpu_driver_version" {
  default     = "LATEST"
  description = "Mode for how the GPU driver is installed."
  type        = string

  validation {
    condition = contains(
      [
        "DEFAULT",
        "GPU_DRIVER_VERSION_UNSPECIFIED",
        "INSTALLATION_DISABLED",
        "LATEST"
      ],
      var.gpu_driver_version
    )
    error_message = "'gpu_driver_version' value is invalid"
  }
}

variable "namespace" {
  default     = "ml-team"
  description = "Name of the namespace to demo."
  type        = string
}

variable "region" {
  default     = "us-central1"
  description = "Region used to create resources"
  type        = string

  validation {
    condition = contains(
      [
        "us-central1",
        "us-east4",
      ],
    var.region)
    error_message = "'region' must be one of ['us-central1', 'us-east4']"
  }
}
