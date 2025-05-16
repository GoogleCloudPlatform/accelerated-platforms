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

locals {
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
}

# Fetch NVIDIA NIM model store bucket
data "google_storage_bucket" "nvidia_nim_model_store" {
  name    = local.nvidia_nim_model_store_bucket_name
  project = local.nvidia_nim_model_store_bucket_project_id
}

# Fetch required secrets
data "google_secret_manager_secret" "ncg_api_key" {
  project   = local.nvidia_ncg_api_key_secret_manager_project_id
  secret_id = local.nvidia_ncg_api_key_secret_manager_secret_name
}

data "google_secret_manager_secret_version" "ncg_api_key" {
  secret = data.google_secret_manager_secret.ncg_api_key.id
}
# Deploy NVIDIA NIM
module "nvidia_nim_llm_deepmind_alphafold2" {
  source = "../../../features/nvidia_nim_llm/"

  cluster_project_id                            = var.cluster_project_id
  kubeconfig_file_name                          = local.kubeconfig_file_name
  nvidia_model_store_bucket_name                = local.nvidia_nim_model_store_bucket_name
  nvidia_model_store_bucket_project_id          = local.nvidia_nim_model_store_bucket_project_id
  nvidia_ncg_api_key_secret_manager_project_id  = data.google_secret_manager_secret.ncg_api_key.project
  nvidia_ncg_api_key_secret_manager_secret_name = data.google_secret_manager_secret.ncg_api_key.secret_id
  nvidia_nim_llm_helm_chart_values = [
    templatefile(
      "${path.module}/templates/deepmind_alphafold2-a100.tftpl.yaml",
      {
      }
    )
  ]
  nvidia_nim_llm_release_name = "deepmind-alphafold2"
}

module "nvidia_nim_llm_meta_llama3_8b_instruct" {
  source = "../../../features/nvidia_nim_llm/"

  cluster_project_id                            = var.cluster_project_id
  kubeconfig_file_name                          = local.kubeconfig_file_name
  nvidia_model_store_bucket_name                = local.nvidia_nim_model_store_bucket_name
  nvidia_model_store_bucket_project_id          = local.nvidia_nim_model_store_bucket_project_id
  nvidia_ncg_api_key_secret_manager_project_id  = data.google_secret_manager_secret.ncg_api_key.project
  nvidia_ncg_api_key_secret_manager_secret_name = data.google_secret_manager_secret.ncg_api_key.secret_id
  nvidia_nim_llm_helm_chart_values = [
    templatefile(
      "${path.module}/templates/meta_llama3-8b-instruct-l4.tftpl.yaml",
      {
      }
    )
  ]
  nvidia_nim_llm_release_name = "meta-llama3-8b-instruct"
}
