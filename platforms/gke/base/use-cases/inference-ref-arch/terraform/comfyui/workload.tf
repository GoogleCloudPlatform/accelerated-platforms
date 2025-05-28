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

resource "local_file" "workload" {
  content = templatefile(
    "${path.module}/templates/workloads/comfyui_${var.comfyui_accelerator_type}.tftpl.yaml",
    {
      namespace      = var.comfyui_kubernetes_namespace,
      app_name       = var.comfyui_app_name,
      accelerator    = var.comfyui_accelerator_type
      image          = local.image_destination
      input_bucket   = google_storage_bucket.comfyui_input.name
      model_buckets  = google_storage_bucket.comfyui_model.name
      output_bucket  = google_storage_bucket.comfyui_output.name
      serviceaccount = local.serviceaccount
    }
  )
  depends_on = [
    null_resource.submit_docker_build,
    google_artifact_registry_repository.comfyui_container_images,
    google_storage_bucket.cloudbuild_source,
    google_service_account.custom_cloudbuild_sa,
    module.kubectl_apply_gateway_res
  ]

  filename = "${local.namespace_manifests_directory}/comfyui_${var.comfyui_accelerator_type}.yaml"
}

module "kubectl_apply_workload_manifest" {
  depends_on = [local_file.workload]

  source                      = "../../../../modules/kubectl_apply"
  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_manifests_directory}/comfyui_${var.comfyui_accelerator_type}.yaml"
  manifest_includes_namespace = true
}
