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

output "cluster_name" {
  value = local.cluster_name
}

output "cluster_project_id" {
  value = var.cluster_project_id
}

output "cluster_region" {
  value = var.cluster_region
}

output "platform_name" {
  value = var.platform_name
}

output "terraform_bucket_name" {
  value = local.terraform_bucket_name
}

output "terraform_project_id" {
  value = var.terraform_project_id
}

output "resource_name_prefix" {
  value = var.resource_name_prefix
}

output "unique_identifier_prefix" {
  value = local.unique_identifier_prefix
}
