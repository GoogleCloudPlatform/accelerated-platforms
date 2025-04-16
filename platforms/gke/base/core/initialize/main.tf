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
  container_node_pool_folder = abspath("${path.module}/../container_node_pool")

  cpu_container_node_pools_directory = "${local.container_node_pool_folder}/cpu/region/${var.cluster_region}"
  cpu_container_node_pool_files      = var.initialize_container_node_pools_cpu ? flatten([for _, file in flatten(fileset("${local.cpu_container_node_pools_directory}", "*.tf")) : "${local.cpu_container_node_pools_directory}/${file}"]) : []

  gpu_container_node_pools_directory = "${local.container_node_pool_folder}/gpu/region/${var.cluster_region}"
  gpu_container_node_pool_files      = var.initialize_container_node_pools_gpu ? flatten([for _, file in flatten(fileset("${local.gpu_container_node_pools_directory}", "*.tf")) : "${local.gpu_container_node_pools_directory}/${file}"]) : []

  tpu_container_node_pools_directory = "${local.container_node_pool_folder}/tpu/region/${var.cluster_region}"
  tpu_container_node_pool_files      = var.initialize_container_node_pools_tpu ? flatten([for _, file in flatten(fileset("${local.tpu_container_node_pools_directory}", "*.tf")) : "${local.tpu_container_node_pools_directory}/${file}"]) : []

  container_node_pool_files = compact(flatten(concat(
    [],
    local.cpu_container_node_pool_files,
    local.gpu_container_node_pool_files,
    local.tpu_container_node_pool_files,
  )))
}

data "google_project" "default" {
  project_id = var.cluster_project_id
}

resource "google_storage_bucket" "terraform" {
  for_each = toset(var.create_terraform_bucket ? ["create"] : [])

  force_destroy               = false
  location                    = var.cluster_region
  name                        = local.terraform_bucket_name
  project                     = data.google_project.default.project_id
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

data "google_storage_bucket" "terraform" {
  depends_on = [google_storage_bucket.terraform]

  name    = local.terraform_bucket_name
  project = data.google_project.default.project_id
}

resource "local_file" "container_node_pools_files_for_region" {
  for_each = toset(local.container_node_pool_files)

  content         = file(each.value)
  file_permission = "0644"
  filename        = "${local.container_node_pool_folder}/${basename(each.value)}"
}
