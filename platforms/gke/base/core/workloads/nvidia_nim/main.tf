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
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  namespace_directory = "${local.manifests_directory_root}/namespace"

  nvidia_nim_llm_models_to_deploy = {
    "deepmind-alphafold2" : "configurations/deepmind_alphafold2.yaml"
    "meta-llama3-8b-instruct" : "configurations/meta_llama3-8b-instruct.yaml"
  }
}

module "nvidia_nim_llm" {
  for_each = local.nvidia_nim_llm_models_to_deploy

  source = "../../../features/nvidia_nim/"

  nvidia_nim_llm_helm_chart_values              = split("\n", file(each.value))
  nvidia_nim_llm_name                           = each.key
  nvidia_ncg_api_key_secret_manager_project_id  = "accelerated-platforms-dev"
  nvidia_ncg_api_key_secret_manager_secret_name = "rueth-nvidia-ncg-api-key"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "namespace_yaml" {
  for_each = local.nvidia_nim_llm_models_to_deploy

  filename = "${local.namespace_directory}/namespace-nim-${each.key}.yaml"
  content = templatefile(
    "${path.module}/templates/namespace.tftpl.yaml",
    {
      namespace = "nim-${each.key}"
    }
  )
}

module "kubectl_apply_namespace" {
  for_each = local.nvidia_nim_llm_models_to_deploy

  source = "../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.namespace_yaml[each.key].filename
  manifest_includes_namespace = true
}

resource "local_file" "manifests" {
  for_each = local.nvidia_nim_llm_models_to_deploy

  filename = "${local.namespace_directory}/nim-${each.key}/manifests.yaml"
  content  = module.nvidia_nim_llm[each.key].manifest
}

module "kubectl_apply_manifests" {
  for_each = local.nvidia_nim_llm_models_to_deploy

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.manifests[each.key].filename
  manifest_includes_namespace = false
  namespace                   = "nim-${each.key}"
}
