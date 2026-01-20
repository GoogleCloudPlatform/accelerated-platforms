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
  kubeconfig_directory = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  ira_inference_perf_bench_directory = "${local.namespaces_directory}/${local.ira_inference_perf_bench_kubernetes_namespace_name}"
  manifests_directory_root           = "${path.module}/../../../../kubernetes/manifests"
  namespaces_directory               = "${local.manifests_directory_root}/namespace"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "serviceaccount_gpu_yaml" {
  content = templatefile(
    "${path.module}/templates/kubernetes/serviceaccount_gpu.tftpl.yaml",
    {
      name      = local.ira_inference_perf_bench_kubernetes_service_account_name
      namespace = local.ira_online_gpu_kubernetes_namespace_name
    }
  )
  filename = "${local.ira_inference_perf_bench_manifests_directory}/serviceaccount-${local.ira_inference_perf_bench_kubernetes_service_account_name}.yaml"
}



module "kubectl_apply_service_account_gpu" {
  depends_on = [
    local_file.serviceaccount_gpu_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.ira_inference_perf_bench_manifests_directory}/serviceaccount-${local.ira_inference_perf_bench_kubernetes_service_account_name}.yaml"
  manifest_includes_namespace = true
}

resource "local_file" "serviceaccount_tpu_yaml" {
  content = templatefile(
    "${path.module}/templates/kubernetes/serviceaccount_tpu.tftpl.yaml",
    {
      name      = local.ira_inference_perf_bench_kubernetes_service_account_name
      namespace = local.ira_online_tpu_kubernetes_namespace_name
    }
  )
  filename = "${local.ira_inference_perf_bench_manifests_directory}/serviceaccount-${local.ira_inference_perf_bench_kubernetes_service_account_name}.yaml"
}

module "kubectl_apply_service_account_tpu" {
  depends_on = [
    local_file.serviceaccount_tpu_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.ira_inference_perf_bench_manifests_directory}/serviceaccount-${local.ira_inference_perf_bench_kubernetes_service_account_name}.yaml"
  manifest_includes_namespace = true
}
