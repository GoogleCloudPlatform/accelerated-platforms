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

#
# Configuration dependencies
# - shared_config/platform_variables.tf
#

locals {
  cloudbuild_cws_default_name = "${local.unique_identifier_prefix}-cws"

  cloudbuild_cws_image_pipeline_connection_name              = var.cloudbuild_cws_image_pipeline_connection_name != null ? var.cloudbuild_cws_image_pipeline_connection_name : "${local.cloudbuild_cws_default_name}-image-pipeline"
  cloudbuild_cws_image_pipeline_git_repository_clone_url     = "https://${var.cloudbuild_cws_image_pipeline_git_provider}/${var.cloudbuild_cws_image_pipeline_git_namespace}/${local.cloudbuild_cws_image_pipeline_git_repository_name}.git"
  cloudbuild_cws_image_pipeline_git_repository_connection_id = "projects/${local.cloudbuild_project_id}/locations/${local.cloudbuild_location}/connections/${local.cloudbuild_cws_image_pipeline_connection_name}/repositories/${local.cloudbuild_cws_image_pipeline_connection_name}"
  cloudbuild_cws_image_pipeline_git_repository_name          = var.cloudbuild_cws_image_pipeline_git_repository_name != null ? var.cloudbuild_cws_image_pipeline_git_repository_name : "${local.cloudbuild_cws_default_name}-image-pipeline"
  cloudbuild_cws_image_pipeline_git_token_file               = var.cloudbuild_cws_image_pipeline_git_token_file != null ? var.cloudbuild_cws_image_pipeline_git_token_file : "secrets/cloudbuild_cws_image_git_token"
  cloudbuild_cws_image_pipeline_git_token_project_id         = var.cloudbuild_cws_image_pipeline_git_token_project_id != null ? var.cloudbuild_cws_image_pipeline_git_token_project_id : local.cloudbuild_project_id
  cloudbuild_cws_image_pipeline_git_token_secret_id          = var.cloudbuild_cws_image_pipeline_git_token_secret_id != null ? var.cloudbuild_cws_image_pipeline_git_token_secret_id : "${local.cloudbuild_cws_default_name}-image-pipeline-git-token"
  cloudbuild_cws_image_pipeline_registry_name                = var.cloudbuild_cws_image_pipeline_registry_name != null ? var.cloudbuild_cws_image_pipeline_registry_name : "${local.cloudbuild_cws_default_name}-cicd"
  cloudbuild_cws_image_pipeline_build_sa_name                = var.cloudbuild_cws_image_pipeline_build_sa_name != null ? var.cloudbuild_cws_image_pipeline_build_sa_name : "${local.unique_identifier_prefix}-cws-ip-build"
  cloudbuild_cws_image_pipeline_build_sa_project_id          = var.cloudbuild_cws_image_pipeline_build_sa_project_id != null ? var.cloudbuild_cws_image_pipeline_build_sa_project_id : local.cloudbuild_project_id
  cloudbuild_cws_image_pipeline_scheduler_sa_name            = var.cloudbuild_cws_image_pipeline_scheduler_sa_name != null ? var.cloudbuild_cws_image_pipeline_scheduler_sa_name : "${local.unique_identifier_prefix}-cws-ip-sched"
  cloudbuild_cws_image_pipeline_scheduler_sa_project_id      = var.cloudbuild_cws_image_pipeline_scheduler_sa_project_id != null ? var.cloudbuild_cws_image_pipeline_scheduler_sa_project_id : local.cloudbuild_project_id

  cloudbuild_cws_image_registry_name          = var.cloudbuild_cws_image_registry_name != null ? var.cloudbuild_cws_image_registry_name : "${local.cloudbuild_cws_default_name}-images"
  cloudbuild_cws_image_registry_url           = "${local.cloudbuild_location}-docker.pkg.dev/${local.cloudbuild_project_id}/${local.cloudbuild_cws_image_registry_name}"
  cloudbuild_cws_image_registry_upstream_name = var.cloudbuild_cws_image_registry_upstream_name != null ? var.cloudbuild_cws_image_registry_upstream_name : "${local.cloudbuild_cws_image_registry_name}-upstream"
  cloudbuild_cws_image_registry_upstream_url  = "${local.cloudbuild_location}-docker.pkg.dev/${local.cloudbuild_project_id}/${local.cloudbuild_cws_image_registry_upstream_name}"

  cloudbuild_location   = var.cloudbuild_location != null ? var.cloudbuild_location : var.platform_default_location
  cloudbuild_project_id = var.cloudbuild_project_id != null ? var.cloudbuild_project_id : var.platform_default_project_id
}

variable "cloudbuild_cws_image_pipeline_commit_changes" {
  default     = true
  description = "Whether to commit changes to the Cloud Workstations image pipeline git repository."
  type        = bool
}

variable "cloudbuild_cws_image_pipeline_connection_name" {
  default     = null
  description = "The name of the Cloud Build repository host connection for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_gh_app_installation_id" {
  default     = null
  description = "The app installation ID for the Cloud Build GitHub App for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_namespace" {
  description = "The Git repository namespace for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_provider" {
  default     = "github.com"
  description = "The Git provider for the Cloud Workstations image pipeline repository."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_repository_name" {
  default     = null
  description = "The Git repository name for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_token_file" {
  default     = null
  description = "The full path to the Git token."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_token_project_id" {
  default     = null
  description = "The project ID of the Secret Manager Git token secret for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_git_token_secret_id" {
  default     = null
  description = "The ID of the Secret Manager Git token secret for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_registry_name" {
  default     = null
  description = "The name of the Artifact Registry repository for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_build_sa_name" {
  default     = null
  description = "The name of the build Google service account for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_build_sa_project_id" {
  default     = null
  description = "The project ID of the build Google service account for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_scheduler_sa_name" {
  default     = null
  description = "The name of the scheduler Google service account for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_pipeline_scheduler_sa_project_id" {
  default     = null
  description = "The project ID of the scheduler Google service account for the Cloud Workstations image pipeline."
  type        = string
}

variable "cloudbuild_cws_image_registry_name" {
  default     = null
  description = "The name of the Artifact Registry repository for Cloud Workstations images."
  type        = string
}

variable "cloudbuild_cws_image_registry_upstream_name" {
  default     = null
  description = "The name of the pull through Artifact Registry repository for upstream Cloud Workstations images."
  type        = string
}

variable "cloudbuild_location" {
  default     = null
  description = "The location to create Cloud Build resource."
  type        = string
}

variable "cloudbuild_project_id" {
  default     = null
  description = "The project ID of Cloud Build project."
  type        = string
}
