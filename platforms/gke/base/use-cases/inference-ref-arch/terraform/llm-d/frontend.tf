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

#Apply gradio frontend manifests
resource "local_file" "gradio" {
  content = templatefile(
    "${path.module}/templates/frontend/gradio.tftpl.yaml",
    {
      namespace           = var.llm-d_kubernetes_namespace
      internal_gateway_ip = "127.0.0.1"
      model_id            = var.llm-d_model_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${var.llm-d_kubernetes_namespace}/frontend/gradio.yaml"
}

module "kubectl_apply_gradio" {
  depends_on = [
    local_file.gradio,
    module.kubectl_apply_namespace,
    module.kubectl_apply_ext_gateway_res,
  ]

  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${var.llm-d_kubernetes_namespace}/frontend/gradio.yaml"
  manifest_includes_namespace = true
}

