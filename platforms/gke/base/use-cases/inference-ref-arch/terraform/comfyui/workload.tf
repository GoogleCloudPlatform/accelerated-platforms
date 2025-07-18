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
  deployment_name = "${var.comfyui_app_name}-${var.comfyui_accelerator_type}"
}

resource "local_file" "workload" {
  depends_on = [
    google_artifact_registry_repository.comfyui_container_images,
    data.google_service_account.cloudbuild,
    data.google_storage_bucket.cloudbuild_source,
    module.kubectl_apply_gateway_res,
    terraform_data.submit_docker_build,
  ]

  content = templatefile(
    "${path.module}/templates/workloads/comfyui-${var.comfyui_accelerator_type}.tftpl.yaml",
    {
      accelerator     = var.comfyui_accelerator_type
      deployment_name = local.deployment_name
      image           = local.image_destination
      input_bucket    = google_storage_bucket.comfyui_input.name
      model_buckets   = google_storage_bucket.comfyui_model.name
      namespace       = var.comfyui_kubernetes_namespace
      output_bucket   = google_storage_bucket.comfyui_output.name
      port            = "${local.comfyui_port}"
      service_name    = local.comfyui_service_name
      serviceaccount  = local.serviceaccount
      workflow_bucket = google_storage_bucket.comfyui_workflow.name
    }
  )
  filename = "${local.manifests_directory}/comfyui-${var.comfyui_accelerator_type}.yaml"
}

module "kubectl_apply_workload_manifest" {
  depends_on = [
    local_file.workload,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.workload.filename
  manifest_includes_namespace = true
}
