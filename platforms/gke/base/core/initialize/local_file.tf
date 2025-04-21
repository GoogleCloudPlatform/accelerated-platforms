
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
  base_directory   = "${path.module}/../../"
  backend_template = "${path.module}/templates/terraform/backend.tf.tftpl"

  core_backend_directories = toset([for _, version_file in local.core_versions_files : trimprefix(trimsuffix(version_file, "/versions.tf"), "../")])
  core_versions_files      = flatten([for _, file in flatten(fileset(local.base_directory, "core/**/versions.tf")) : file])

  shared_config_folder = "${path.module}/../../_shared_config"

  use_case_backend_directories = var.initialize_backend_use_case_name != null ? toset([for _, version_file in local.use_case_versions_files : trimprefix(trimsuffix(dirname(version_file), "/versions.tf"), "../")]) : []
  use_case_versions_files      = var.initialize_backend_use_case_name != null ? flatten([for _, file in flatten(fileset("${local.base_directory}/use-cases", "${var.initialize_backend_use_case_name}/**/versions.tf")) : file]) : []
}

resource "local_file" "core_backend_tf" {
  for_each = local.core_backend_directories
  content = templatefile(
    local.backend_template,
    {
      bucket = local.terraform_bucket_name,
      prefix = "terraform/${each.key}",
    }
  )
  file_permission = "0644"
  filename        = "${local.base_directory}/${each.key}/backend.tf"
}

resource "local_file" "shared_config_cluster_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      cluster_auto_monitoring_config_scope                 = var.cluster_auto_monitoring_config_scope
      cluster_binary_authorization_evaluation_mode         = var.cluster_binary_authorization_evaluation_mode
      cluster_confidential_nodes_enabled                   = var.cluster_confidential_nodes_enabled
      cluster_database_encryption_key_name                 = var.cluster_database_encryption_key_name
      cluster_database_encryption_state                    = var.cluster_database_encryption_state
      cluster_enable_private_endpoint                      = var.cluster_enable_private_endpoint
      cluster_gateway_api_config_channel                   = var.cluster_gateway_api_config_channel
      cluster_gpu_driver_version                           = var.cluster_gpu_driver_version
      cluster_master_global_access_enabled                 = var.cluster_master_global_access_enabled
      cluster_master_ipv4_cidr_block                       = var.cluster_master_ipv4_cidr_block
      cluster_node_auto_provisioning_enabled               = var.cluster_node_auto_provisioning_enabled
      cluster_node_auto_provisioning_resource_limits       = var.cluster_node_auto_provisioning_resource_limits
      cluster_node_pool_default_service_account_id         = var.cluster_node_pool_default_service_account_id
      cluster_node_pool_default_service_account_project_id = var.cluster_node_pool_default_service_account_project_id
      cluster_private_endpoint_subnetwork                  = var.cluster_private_endpoint_subnetwork
      cluster_project_id                                   = var.cluster_project_id
      cluster_region                                       = var.cluster_region
      cluster_system_node_pool_machine_type                = var.cluster_system_node_pool_machine_type
      cluster_use_connect_gateway                          = var.cluster_use_connect_gateway
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/cluster.auto.tfvars"
}

resource "local_file" "shared_config_configmanagement_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      configmanagement_git_credentials = var.configmanagement_git_credentials
      configmanagement_policy_dir      = var.configmanagement_policy_dir
      configmanagement_prevent_drift   = var.configmanagement_prevent_drift
      configmanagement_sync_branch     = var.configmanagement_sync_branch
      configmanagement_sync_repo       = var.configmanagement_sync_repo
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/configmanagement.auto.tfvars"
}

resource "local_file" "shared_config_initialize_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      initialize_backend_use_case_name    = var.initialize_backend_use_case_name
      initialize_container_node_pools_cpu = var.initialize_container_node_pools_cpu
      initialize_container_node_pools_gpu = var.initialize_container_node_pools_gpu
      initialize_container_node_pools_tpu = var.initialize_container_node_pools_tpu
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/initialize.auto.tfvars"
}

resource "local_file" "shared_config_networking_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      dynamic_routing_mode = var.dynamic_routing_mode
      nat_gateway_name     = var.nat_gateway_name
      network_name         = var.network_name
      router_name          = var.router_name
      subnet_cidr_range    = var.subnet_cidr_range
      subnetwork_name      = var.subnetwork_name
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/networking.auto.tfvars"
}

resource "local_file" "shared_config_platform_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      platform_name        = var.platform_name
      resource_name_prefix = var.resource_name_prefix
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/platform.auto.tfvars"
}

resource "local_file" "shared_config_terraform_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      create_terraform_bucket = var.create_terraform_bucket
      terraform_project_id    = var.terraform_project_id
      terraform_write_tfvars  = var.terraform_write_tfvars
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/terraform.auto.tfvars"
}

resource "local_file" "shared_config_workloads_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      #inference_gateway_version = var.inference_gateway_version
      jobset_version = var.jobset_version
      kueue_version  = var.kueue_version
      lws_version    = var.lws_version
    }
  )
  file_permission = "0644"
  filename        = "${local.shared_config_folder}/workloads.auto.tfvars"
}

resource "local_file" "use_case_backend_tf" {
  for_each = local.use_case_backend_directories
  content = templatefile(
    local.backend_template,
    {
      bucket = local.terraform_bucket_name,
      prefix = "terraform/${each.key}",
    }
  )
  file_permission = "0644"
  filename        = "${local.base_directory}/use-cases/${each.key}/backend.tf"
}
