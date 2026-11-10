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

locals {
  agent_substrate_project_id                    = var.agent_substrate_project_id != null ? var.agent_substrate_project_id : var.platform_default_project_id
  agent_substrate_ar_repository_name            = var.agent_substrate_ar_repository_name != null ? var.agent_substrate_ar_repository_name : trimsuffix(substr("${local.unique_identifier_prefix}-agent-substrate", 0, 63), "-")
  agent_substrate_snapshot_bucket_name          = var.agent_substrate_snapshot_bucket_name != null ? var.agent_substrate_snapshot_bucket_name : trimsuffix(substr("${local.agent_substrate_project_id}-${local.unique_identifier_prefix}-ate-snapshots", 0, 63), "-")
  agent_substrate_snapshot_bucket_force_destroy = var.agent_substrate_snapshot_bucket_force_destroy
  agent_substrate_snapshot_transfer_gsa_name    = trimsuffix(substr("${local.unique_identifier_prefix}-ate-snapshot", 0, 28), "-")
  agent_substrate_atespace_name                 = var.agent_substrate_atespace_name != null ? var.agent_substrate_atespace_name : "security-demo"
  agent_substrate_workload_namespace            = var.agent_substrate_workload_namespace != null ? var.agent_substrate_workload_namespace : "agent-sandbox"
  agent_substrate_secrets_namespace             = var.agent_substrate_secrets_namespace != null ? var.agent_substrate_secrets_namespace : "agent-secrets"
  agent_substrate_version                       = var.agent_substrate_version != null ? var.agent_substrate_version : "v1.0.0"
  agent_substrate_min_gke_version               = var.agent_substrate_min_gke_version != null ? var.agent_substrate_min_gke_version : "1.37"
  agent_substrate_node_machine_type             = var.agent_substrate_node_machine_type != null ? var.agent_substrate_node_machine_type : "n4-standard-4"
  agent_substrate_node_locations                = var.agent_substrate_node_locations
  agent_substrate_node_disk_type                = var.agent_substrate_node_disk_type != null ? var.agent_substrate_node_disk_type : (can(regex("^(c4|n4)-", local.agent_substrate_node_machine_type)) ? "hyperdisk-balanced" : "pd-balanced")
}

variable "agent_substrate_ar_repository_name" {
  default     = null
  description = "The Artifact Registry Docker repository name for the Agent Substrate Google ADK demo container image."
  type        = string
}

variable "agent_substrate_atespace_name" {
  default     = null
  description = "The Agent Substrate atespace name used for the 4-Act security detonation demo."
  type        = string
}

variable "agent_substrate_min_gke_version" {
  default     = null
  description = "Minimum GKE control-plane and worker-node Kubernetes minor version required by Agent Substrate (defaults to 1.37)."
  type        = string
}

variable "agent_substrate_node_disk_type" {
  default     = null
  description = "Boot disk type for the Agent Substrate worker node pool. Defaults to hyperdisk-balanced for C4/N4 and pd-balanced for C3/E2."
  type        = string
}

variable "agent_substrate_node_locations" {
  default     = null
  description = "Optional list of zones for the Agent Substrate worker node pool when overriding default regional zone selection due to stockouts."
  type        = list(string)
}

variable "agent_substrate_node_machine_type" {
  default     = null
  description = "Machine type for the Agent Substrate worker node pool (for example: c4-standard-4, n4-standard-4, or c3-standard-4)."
  type        = string
}

variable "agent_substrate_project_id" {
  default     = null
  description = "The GCP project ID for the Agent Substrate security demo resources."
  type        = string
}

variable "agent_substrate_secrets_namespace" {
  default     = null
  description = "The isolated Kubernetes namespace holding raw credentials for k8s-credential-provider and partner-api."
  type        = string
}

variable "agent_substrate_snapshot_bucket_force_destroy" {
  default     = true
  description = "Whether Terraform destroy deletes cached Golden Tags and actor memory checkpoints inside the snapshot bucket."
  type        = bool
}

variable "agent_substrate_snapshot_bucket_name" {
  default     = null
  description = "The Cloud Storage bucket name for storing Agent Substrate Golden Tags and memory checkpoints."
  type        = string
}

variable "agent_substrate_version" {
  default     = null
  description = "The Agent Substrate release tag to deploy (for example, v1.0.0)."
  type        = string
}

variable "agent_substrate_workload_namespace" {
  default     = null
  description = "The Kubernetes namespace hosting the Agent Substrate WorkerPool, split-plane gateway, and Prometheus UI."
  type        = string
}
