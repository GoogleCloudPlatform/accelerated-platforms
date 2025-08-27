
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

resource "local_file" "shared_config_platform_auto_tfvars" {
  for_each = toset(var.terraform_write_tfvars ? ["write"] : [])

  content = provider::terraform::encode_tfvars(
    {
      platform_custom_role_unique_suffix = local.platform_custom_role_unique_suffix
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

  lifecycle {
    prevent_destroy = true
  }
}
