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
  _template_backend = "${path.module}/templates/backend.config.tpl"

  backend = templatefile(local._template_backend, {
    bucket = data.google_storage_bucket.terraform.name
  })

  use_case_terraservices = [
    # Don't configure the remote backend for the initialize terraservice
    # because we use a local backend for that in order to solve a
    # chicken-and-egg issue where the initialize terraservice depends on
    # the configuration files that the initialize terraservice creates.
    # Keeping this as a reference if we change idea in the future
    # abspath("${path.module}"),
    abspath("${path.module}/../container_image_repository"),
  ]
}

data "google_project" "default" {
  project_id = var.cluster_project_id
}

data "google_storage_bucket" "terraform" {
  name    = local.terraform_bucket_name
  project = data.google_project.default.project_id
}

resource "local_file" "backend" {
  for_each = toset(local.use_case_terraservices)

  file_permission = "0644"
  filename        = "${each.value}/backend.config"
  content         = try(local.backend, null)
}
