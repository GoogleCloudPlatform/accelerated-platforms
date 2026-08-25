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

resource "local_file" "llmd_ob_gateway_kustomization" {
  content = templatefile(
    "${path.module}/../_shared_config/templates/gateway/kustomization.yaml.tftpl",
    {
      remote_manifest = local.llmd_ob_gateway_remote_manifest
    }
  )
  filename = "${path.module}/.terraform/manifests/gateway-kustomize/kustomization.yaml"
}

resource "local_file" "llmd_ob_gcp_backend_policy_override" {
  content = templatefile(
    "${path.module}/../_shared_config/templates/gateway/gcp-backend-policy-override.yaml.tftpl",
    {
      name      = "optimized-baseline"
      namespace = local.llmd_namespace
    }
  )
  filename = "${path.module}/.terraform/manifests/gateway-kustomize/gcp-backend-policy-override.yaml"
}

module "kubectl_apply_llmd_ob_gateway_manifests" {
  depends_on = [
    local_file.llmd_ob_gateway_kustomization,
    local_file.llmd_ob_gcp_backend_policy_override,
  ]

  source                      = "../../../../../modules/kubectl_apply"
  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = dirname(local_file.llmd_ob_gateway_kustomization.filename)
  manifest_includes_namespace = false
  namespace                   = local.llmd_namespace
  use_kustomize               = true
}

