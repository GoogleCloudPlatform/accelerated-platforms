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

#data "github_app" "cloudbuild" {
#  slug = "google-cloud-build"
#}

# module "github_repository" {
#   for_each = toset(var.cloudbuild_cws_image_pipeline_git_repository_name == null ? ["managed"] : [])

#   source = "../../../../../terraform/modules/github/repository"

#   providers = {
#     github = github
#   }

#   branches = {
#     default = "main"
#     names   = ["main"]
#   }
#   description = "${local.unique_identifier_prefix} Cloud Workstations image pipeline"
#   name        = local.cloudbuild_cws_image_pipeline_git_repository_name
# }
