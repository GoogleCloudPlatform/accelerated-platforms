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

variable "gke_gateway_kubernetes_namespace_name" {
  default     = "gke-gateway"
  description = "Namespace for the GKE gateway resources."
  type        = string
}

variable "gke_gateway_class_names" {
  default = [
    "gke-l7-global-external-managed",
    "gke-l7-regional-external-managed",
  ]
  description = "List of gateway class names to create gateways for."
  type        = list(string)
}
