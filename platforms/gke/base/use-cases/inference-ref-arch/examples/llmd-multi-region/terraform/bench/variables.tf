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

variable "bucket_location" {
  description = "Location (region) of the benchmark results bucket. Use the config cluster region."
  type        = string
}

variable "bucket_name" {
  description = "Name of the benchmark results bucket."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace of the benchmark client Jobs. Identical in every cluster (namespace sameness)."
  type        = string
}

variable "kubernetes_service_account" {
  description = "Kubernetes service account that the benchmark client Jobs run as."
  type        = string
}

variable "project_id" {
  description = "Project that hosts the clusters and the results bucket."
  type        = string
}

variable "results_retention_days" {
  default     = 30
  description = "Benchmark result objects older than this many days are deleted."
  type        = number
}
