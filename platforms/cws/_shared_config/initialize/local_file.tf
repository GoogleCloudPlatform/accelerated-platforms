
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
  base_directory   = "${path.module}/../.."
  backend_template = "${path.module}/templates/terraform/backend.tf.tftpl"

  backend_directories = toset([for _, version_file in local.versions_files : trimprefix(trimsuffix(version_file, "/versions.tf"), "../")])
  versions_files      = concat(flatten([for _, file in flatten(fileset(local.base_directory, "**/versions.tf")) : file if !strcontains(file, "_shared_config")]), ["_shared_config/initialize/versions.tf"])

  platform_custom_role_unique_suffix = var.platform_custom_role_unique_suffix != "null" ? var.platform_custom_role_unique_suffix : terraform_data.unique_timestamps.input.unix

  shared_config_folder = "${path.module}/../../_shared_config"
}

resource "time_static" "unique" {
}

resource "terraform_data" "unique_timestamps" {
  input = {
    day    = formatdate("YYYYMMDD", time_static.unique.rfc3339)
    hour   = formatdate("YYYYMMDDhh", time_static.unique.rfc3339)
    min    = formatdate("YYYYMMDDhhmm", time_static.unique.rfc3339)
    month  = formatdate("YYYYMM", time_static.unique.rfc3339)
    second = formatdate("YYYYMMDDhhmmss", time_static.unique.rfc3339)
    unix   = time_static.unique.unix
    year   = formatdate("YYYY", time_static.unique.rfc3339)
  }
}

resource "local_file" "backend_tf" {
  depends_on = [
    data.google_storage_bucket.terraform
  ]

  for_each = local.backend_directories

  content = templatefile(
    local.backend_template,
    {
      bucket = local.terraform_bucket_name,
      prefix = "terraform/cws/${replace(each.key, "//terraform//", "/")}",
    }
  )
  file_permission = "0644"
  filename        = "${local.base_directory}/${each.key}/backend.tf"
}

resource "local_file" "shared_config_build_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      cloudbuild_cws_image_pipeline_commit_changes          = var.cloudbuild_cws_image_pipeline_commit_changes
      cloudbuild_cws_image_pipeline_connection_name         = var.cloudbuild_cws_image_pipeline_connection_name
      cloudbuild_cws_image_pipeline_gh_app_installation_id  = var.cloudbuild_cws_image_pipeline_gh_app_installation_id
      cloudbuild_cws_image_pipeline_git_namespace           = var.cloudbuild_cws_image_pipeline_git_namespace
      cloudbuild_cws_image_pipeline_git_provider            = var.cloudbuild_cws_image_pipeline_git_provider
      cloudbuild_cws_image_pipeline_git_repository_name     = var.cloudbuild_cws_image_pipeline_git_repository_name
      cloudbuild_cws_image_pipeline_git_token_file          = var.cloudbuild_cws_image_pipeline_git_token_file
      cloudbuild_cws_image_pipeline_git_token_project_id    = var.cloudbuild_cws_image_pipeline_git_token_project_id
      cloudbuild_cws_image_pipeline_git_token_secret_id     = var.cloudbuild_cws_image_pipeline_git_token_secret_id
      cloudbuild_cws_image_pipeline_registry_name           = var.cloudbuild_cws_image_pipeline_registry_name
      cloudbuild_cws_image_pipeline_build_sa_name           = var.cloudbuild_cws_image_pipeline_build_sa_name
      cloudbuild_cws_image_pipeline_build_sa_project_id     = var.cloudbuild_cws_image_pipeline_build_sa_project_id
      cloudbuild_cws_image_pipeline_scheduler_sa_name       = var.cloudbuild_cws_image_pipeline_scheduler_sa_name
      cloudbuild_cws_image_pipeline_scheduler_sa_project_id = var.cloudbuild_cws_image_pipeline_scheduler_sa_project_id
      cloudbuild_cws_image_registry_name                    = var.cloudbuild_cws_image_registry_name
      cloudbuild_cws_image_registry_upstream_name           = var.cloudbuild_cws_image_registry_upstream_name
      cloudbuild_location                                   = var.cloudbuild_location
      cloudbuild_project_id                                 = var.cloudbuild_project_id
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/build.auto.tfvars"
}

resource "local_file" "shared_config_comfyui_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      cws_comfyui_model_bucket_location   = var.cws_comfyui_model_bucket_location
      cws_comfyui_model_bucket_name       = var.cws_comfyui_model_bucket_name
      cws_comfyui_model_bucket_project_id = var.cws_comfyui_model_bucket_project_id
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/comfyui.auto.tfvars"
}

resource "local_file" "shared_config_networking_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      cws_nat_gateway_name         = var.cws_nat_gateway_name
      cws_network_name             = var.cws_network_name
      cws_network_routing_mode     = var.cws_network_routing_mode
      cws_router_name              = var.cws_router_name
      cws_subnetwork_ip_cidr_range = var.cws_subnetwork_ip_cidr_range
      cws_subnetwork_name          = var.cws_subnetwork_name
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/networking.auto.tfvars"
}

resource "local_file" "shared_config_platform_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      platform_custom_role_unique_suffix = local.platform_custom_role_unique_suffix
      platform_default_location          = var.platform_default_location
      platform_default_project_id        = var.platform_default_project_id
      platform_name                      = var.platform_name
      platform_resource_name_prefix      = var.platform_resource_name_prefix
      terraform_bucket_name              = var.terraform_bucket_name
      terraform_project_id               = var.terraform_project_id
      terraform_write_tfvars             = var.terraform_write_tfvars
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/platform.auto.tfvars"
}

resource "local_file" "shared_config_workstation_cluster_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      workstation_cluster_name                       = var.workstation_cluster_name
      workstation_cluster_project_id                 = var.workstation_cluster_project_id
      workstation_cluster_region                     = var.workstation_cluster_region
      workstation_cluster_service_account_id         = var.workstation_cluster_service_account_id
      workstation_cluster_service_account_project_id = var.workstation_cluster_service_account_project_id
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/workstation_cluster.auto.tfvars"
}
