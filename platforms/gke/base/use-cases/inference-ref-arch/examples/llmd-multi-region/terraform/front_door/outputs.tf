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

output "address" {
  description = "Global static external IPv4 address of the front door."
  value       = google_compute_global_address.front_door.address
}

output "address_name" {
  description = "Name of the global address, referenced by the Gateway as a NamedAddress."
  value       = google_compute_global_address.front_door.name
}

output "hostname" {
  description = "Host name of the front door (Cloud Endpoints DNS)."
  value       = google_endpoints_service.front_door.service_name
}

output "security_policy_name" {
  description = "Name of the Cloud Armor backend security policy, or an empty string when Cloud Armor is disabled."
  value       = var.cloud_armor_enabled ? google_compute_security_policy.front_door[0].name : ""
}

output "ssl_certificate_name" {
  description = "Name of the Google-managed SSL certificate, referenced by the Gateway with networking.gke.io/pre-shared-certs."
  value       = google_compute_managed_ssl_certificate.front_door.name
}

output "ssl_policy_name" {
  description = "Name of the SSL policy, referenced by the GCPGatewayPolicy."
  value       = google_compute_ssl_policy.front_door.name
}

output "url" {
  description = "URL of the front door."
  value       = "https://${google_endpoints_service.front_door.service_name}"
}
