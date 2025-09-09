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
  container_node_pool_folder = "${path.module}/../container_node_pool"

  cpu_container_node_pools_directory = "${local.container_node_pool_folder}/cpu/region/${local.cluster_region}"
  cpu_container_node_pool_files      = var.initialize_container_node_pools_cpu ? flatten([for _, file in flatten(fileset("${local.cpu_container_node_pools_directory}", "*.tf")) : "${local.cpu_container_node_pools_directory}/${file}"]) : []

  gpu_container_node_pools_directory = "${local.container_node_pool_folder}/gpu/region/${local.cluster_region}"

  rtx_filename_string = "_rtx"

  gpu_without_rtx_container_node_pool_files = var.initialize_container_node_pools_gpu && var.initialize_container_node_pools_gpu_without_rtx ? flatten([for _, file in flatten(fileset("${local.gpu_container_node_pools_directory}", "*.tf")) : "${local.gpu_container_node_pools_directory}/${file}" if !strcontains(file, local.rtx_filename_string)]) : []
  gpu_with_rtx_container_node_pool_files    = var.initialize_container_node_pools_gpu && var.initialize_container_node_pools_gpu_with_rtx ? flatten([for _, file in flatten(fileset("${local.gpu_container_node_pools_directory}", "*.tf")) : "${local.gpu_container_node_pools_directory}/${file}" if strcontains(file, local.rtx_filename_string)]) : []

  tpu_container_node_pools_directory = "${local.container_node_pool_folder}/tpu/region/${local.cluster_region}"
  tpu_container_node_pool_files      = var.initialize_container_node_pools_tpu ? flatten([for _, file in flatten(fileset("${local.tpu_container_node_pools_directory}", "*.tf")) : "${local.tpu_container_node_pools_directory}/${file}"]) : []

  container_node_pool_files = compact(flatten(concat(
    [],
    local.cpu_container_node_pool_files,
    local.gpu_without_rtx_container_node_pool_files,
    local.gpu_with_rtx_container_node_pool_files,
    local.tpu_container_node_pool_files,
  )))
}

resource "google_storage_bucket" "terraform" {
  for_each = toset(var.create_terraform_bucket ? ["create"] : [])

  force_destroy               = false
  location                    = local.cluster_region
  name                        = local.terraform_bucket_name
  project                     = data.google_project.terraform.project_id
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

data "google_storage_bucket" "terraform" {
  depends_on = [google_storage_bucket.terraform]

  name    = local.terraform_bucket_name
  project = data.google_project.terraform.project_id
}

resource "local_file" "container_node_pools_files_for_region" {
  for_each = toset(local.container_node_pool_files)

  content         = file(each.value)
  file_permission = "0644"
  filename        = "${local.container_node_pool_folder}/${basename(each.value)}"
}
