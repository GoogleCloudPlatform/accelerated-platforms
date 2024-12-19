
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
