# Copyright 2026 Google LLC
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

output "agent_substrate_ar_repository_name" {
  value = local.agent_substrate_ar_repository_name
}

output "agent_substrate_atespace_name" {
  value = local.agent_substrate_atespace_name
}

output "agent_substrate_min_gke_version" {
  value = local.agent_substrate_min_gke_version
}

output "agent_substrate_node_disk_type" {
  value = local.agent_substrate_node_disk_type
}

output "agent_substrate_node_locations" {
  value = local.agent_substrate_node_locations
}

output "agent_substrate_node_machine_type" {
  value = local.agent_substrate_node_machine_type
}

output "agent_substrate_project_id" {
  value = local.agent_substrate_project_id
}

output "agent_substrate_secrets_namespace" {
  value = local.agent_substrate_secrets_namespace
}

output "agent_substrate_snapshot_bucket_force_destroy" {
  value = local.agent_substrate_snapshot_bucket_force_destroy
}

output "agent_substrate_snapshot_bucket_name" {
  value = local.agent_substrate_snapshot_bucket_name
}

output "agent_substrate_snapshot_transfer_gsa_name" {
  value = local.agent_substrate_snapshot_transfer_gsa_name
}

output "agent_substrate_version" {
  value = local.agent_substrate_version
}

output "agent_substrate_workload_namespace" {
  value = local.agent_substrate_workload_namespace
}
