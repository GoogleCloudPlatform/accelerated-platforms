
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
  acp_root             = "${path.module}/../../../../../../.."
  local_directory      = "platforms/cws/image_pipeline/terraform/images/comfyui/models/repo_files"
  repositories_path    = "platforms/cws/image_pipeline/repositories"
  repository_directory = "${local.repositories_path}/repository-${local.unique_identifier_prefix}"
  repository_folder    = "${path.module}/../../../../repository-${local.unique_identifier_prefix}"
}
