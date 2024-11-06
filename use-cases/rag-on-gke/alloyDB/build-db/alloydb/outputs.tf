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

output "cluster_id" {
  description = "ID of the Alloy DB Cluster created"
  value       = google_alloydb_cluster.default.id
}

output "primary_instance_id" {
  description = "ID of the primary instance created"
  value       = google_alloydb_instance.primary.id
}

output "primary_psc_attachment_link" {
  description = "The private service connect (psc) attachment created for primary instance"
  value       = try(google_alloydb_instance.primary.psc_instance_config[0].service_attachment_link, "")
}

output "primary_psc_dns_name" {
  description = "The DNS name of the instance for PSC connectivity created for primary instance"
  value       = try(google_alloydb_instance.primary.psc_instance_config[0].psc_dns_name, "")
}

output "read_instance_ids" {
  description = "IDs of the read instances created"
  value = [
    for rd, details in google_alloydb_instance.read_pool : details.id
  ]
}

output "read_psc_attachment_links" {
  description = "The private service connect (psc) attachment created read replica instances"
  value = try([
    for rd, details in google_alloydb_instance.read_pool : details.psc_instance_config[0].service_attachment_link
  ], "")
}

output "read_psc_dns_names" {
  description = "The DNS names of the instances for PSC connectivity created for replica instances"
  value = try([
    for rd, details in google_alloydb_instance.read_pool : details.psc_instance_config[0].service_attachment_link
  ], "")
}

output "cluster_name" {
  description = "ID of the Alloy DB Cluster created"
  value       = google_alloydb_cluster.default.name
}

output "cluster" {
  description = "Cluster created"
  value       = resource.google_alloydb_cluster.default
}

output "primary_instance" {
  description = "Primary instance created"
  value       = resource.google_alloydb_instance.primary
}

output "replica_instances" {
  description = "Replica instances created"
  value       = resource.google_alloydb_instance.read_pool
}
