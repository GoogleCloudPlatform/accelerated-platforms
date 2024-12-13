
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
  backend_directories = toset([for _, v in local.versions_files : trimprefix(trimsuffix(dirname(v), "/versions.tf"), "../")])
  backend_template    = "${path.module}/templates/terraform/backend.tf.tftpl"
  terraservice_path   = "${path.module}/.."
  versions_files      = flatten([for _, v in flatten(fileset("${local.terraservice_path}/", "**/versions.tf")) : v])
}

resource "local_file" "backend_tf" {
  for_each = local.backend_directories
  content = templatefile(
    local.backend_template,
    {
      bucket = local.terraform_bucket_name,
      prefix = "terraform/${each.key}",
    }
  )
  file_permission = "0644"
  filename        = "${local.terraservice_path}/${each.key}/backend.tf"
}
