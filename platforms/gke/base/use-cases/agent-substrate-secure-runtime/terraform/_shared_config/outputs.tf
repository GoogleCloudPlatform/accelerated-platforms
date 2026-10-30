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

output "secure_runtime_agent_image_url" {
  value = local.secure_runtime_agent_image_url
}

output "secure_runtime_agent_namespace" {
  value = var.secure_runtime_agent_namespace
}

output "secure_runtime_agent_service_account" {
  value = var.secure_runtime_agent_service_account
}

output "secure_runtime_gemini_model" {
  value = var.secure_runtime_gemini_model
}

output "secure_runtime_github_repo" {
  value = var.secure_runtime_github_repo
}

output "secure_runtime_intent_extproc_image_url" {
  value = local.secure_runtime_intent_extproc_image_url
}

output "secure_runtime_runner_image_url" {
  value = local.secure_runtime_runner_image_url
}

output "use_case" {
  value = "agent-substrate-secure-runtime"
}
