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

output "build_ar_docker_hub_remote_repository_url" {
  value = local.build_ar_docker_hub_remote_repository_url
}

output "build_location" {
  value = var.build_location
}

output "build_project_id" {
  value = var.build_project_id
}

output "build_terraform_bucket_name" {
  value = local.build_terraform_bucket_name
}
