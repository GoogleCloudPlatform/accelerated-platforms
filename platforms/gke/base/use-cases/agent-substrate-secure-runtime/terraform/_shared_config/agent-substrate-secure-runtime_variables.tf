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
  acp_root = abspath("${path.module}/../../../../../..")

  secure_runtime_runner_image_url         = "${local.cloudbuild_ar_image_repository_url}/secure-runtime-runner:${var.secure_runtime_image_tag}"
  secure_runtime_intent_extproc_image_url = "${local.cloudbuild_ar_image_repository_url}/secure-runtime-intent-extproc:${var.secure_runtime_image_tag}"
  secure_runtime_agent_image_url          = "${local.cloudbuild_ar_image_repository_url}/secure-runtime-agent:${var.secure_runtime_image_tag}"
}

variable "secure_runtime_image_tag" {
  default     = "1.0.0"
  description = "Tag for the Secure Runtime container images built in Artifact Registry."
  type        = string
}

variable "secure_runtime_gemini_model" {
  default     = "gemini-2.5-flash"
  description = "Vertex AI Gemini model used by the ADK GitHub Triage Agent."
  type        = string
}

variable "secure_runtime_github_repo" {
  default     = "demo-org/secure-runtime-sandbox-demo"
  description = "Dedicated private GitHub repository (owner/repo) triaged by the agent."
  type        = string
}

variable "secure_runtime_github_readonly_token" {
  default     = "ghp_replace_with_fine_grained_readonly_pat"
  description = "Fine-grained read-only GitHub token stored in agent-credentials/github-readonly-token for out-of-sandbox header injection by atenet-egress."
  sensitive   = true
  type        = string
}

variable "secure_runtime_agent_namespace" {
  default     = "agent-harness"
  description = "Kubernetes namespace for the ADK GitHub Triage Agent harness."
  type        = string
}

variable "secure_runtime_agent_service_account" {
  default     = "triage-agent"
  description = "Kubernetes ServiceAccount for the ADK GitHub Triage Agent."
  type        = string
}
