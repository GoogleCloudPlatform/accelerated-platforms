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

module "kubectl_apply_llmd_ppcr_gateway_manifests" {
  source                      = "../../../../../modules/kubectl_apply"
  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.llmd_ppcr_gateway_remote_manifest
  manifest_includes_namespace = false
  namespace                   = local.llmd_namespace
  use_kustomize               = true
}
