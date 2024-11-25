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

output "project_id" {
  description = "Project ID of the Alloy DB Cluster created"
  value       = var.project_id
}

output "cluster_id" {
  description = "ID of the Alloy DB Cluster created"
  value       = module.alloydb_cluster.cluster_id
}

output "primary_instance_id" {
  description = "ID of the primary instance created"
  value       = module.alloydb_cluster.primary_instance_id
}

output "primary_instance_ip" {
  description = "IP address of the primary instance"
  value       = module.alloydb_cluster.primary_instance.ip_address
}

output "cluster_name" {
  description = "The name of the cluster resource"
  value       = module.alloydb_cluster.cluster_name
}

output "region" {
  description = "The region for primary cluster"
  value       = var.region
}
