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

data "helm_template" "llmd_gaie_stack" {
  name         = "gaie-${local.llmd_release_name}"
  namespace    = var.llmd_kubernetes_namespace
  kube_version = var.kubernetes_version
  #create_namespace = var.kubernetes_namespace_create

  #  repository = var.llmd_infra_repo
  chart   = var.gaie_chart
  version = var.gaie_chart_version
  values = [
    file("${path.module}/helm_values/gaie_values.yaml"),

    # 2. GKE Specific Overrides (equivalent to the 'if eq gke' block)
    yamlencode({
      provider = {
        name = "gke"
      }
      inferencePool = {
        apiVersion = local.gaie_values.inferencePool.apiVersion # from configuration_values.yaml
      }
      inferenceExtension = {
        monitoring = {
          gke = {
            enabled = true
          }
          prometheus = {
            enabled = false
          }
        }
      }
    })
  ]
  skip_tests = var.skip_tests
  validate   = var.validate_manifests
}


resource "local_file" "llmd_gaie_manifests" {
  filename = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/gaie/gaie.yaml"
  content  = data.helm_template.llmd_gaie_stack.manifest
}


module "kubectl_apply_llmd_gaie_manifests" {
  source                      = "../../../../modules/kubectl_apply"
  depends_on                  = [module.kubectl_apply_namespace, module.kubectl_apply_int_gateway_res]
  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.llmd_gaie_manifests.filename
  manifest_includes_namespace = false
  namespace                   = var.llmd_kubernetes_namespace
}
