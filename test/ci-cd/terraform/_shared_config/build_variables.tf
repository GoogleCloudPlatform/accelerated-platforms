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
  build_ar_docker_hub_remote_repository_name = "docker-io"
  build_ar_docker_hub_remote_repository_url  = "${var.build_location}-docker.pkg.dev/${var.build_project_id}/${local.build_ar_docker_hub_remote_repository_name}"
  build_github_token_secret                  = "github-token"
  build_huggingface_token_read_secret        = "huggingface-hub-access-token-read"
  build_huggingface_token_write_secret       = "huggingface-hub-access-token-write"
  build_ngc_api_key_secret                   = "ngc-api-key"
  build_terraform_bucket_name                = "${var.build_project_id}-build-terraform"
}

variable "build_location" {
  description = "The Google Cloud location to use when creating resources for the 'build' project."
  type        = string
}

variable "build_project_id" {
  description = "The Google Cloud project ID for the 'build' project."
  type        = string
}
