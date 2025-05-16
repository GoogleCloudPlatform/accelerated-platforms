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

data "google_secret_manager_secret" "ncg_api_key" {
  project   = var.nvidia_ncg_api_key_secret_manager_project_id
  secret_id = var.nvidia_ncg_api_key_secret_manager_secret_name
}

data "google_secret_manager_secret_version" "ncg_api_key" {
  secret = data.google_secret_manager_secret.ncg_api_key.id
}

data "helm_template" "nvidia_nim_llm" {
  chart               = "https://helm.ngc.nvidia.com/nim/charts/nim-llm-${var.nvidia_nim_llm_helm_chart_version}.tgz"
  kube_version        = "1.23"
  name                = var.nvidia_nim_llm_name
  repository_password = data.google_secret_manager_secret_version.ncg_api_key.secret_data
  repository_username = "$oauthtoken"

  values = var.nvidia_nim_llm_helm_chart_values
}
