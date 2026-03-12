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

###############################################################################
# This file create resources required for internal gateway supported by
# llmd inference scheduler for intelligent routing
###############################################################################


resource "google_compute_address" "internal_gateway_ip" {
  project      = data.google_project.cluster.project_id
  name         = "llm-inference-gw-ip"
  subnetwork   = local.network_cluster_subnet_node_name
  address_type = "INTERNAL"
  purpose      = "GCE_ENDPOINT"
  region       = var.cluster_region
}

resource "local_file" "gateway_internal_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/gateway-internal.tftpl.yaml",
    {
      gateway_name        = local.llmd_gateway_name_internal
      namespace           = var.llmd_kubernetes_namespace
      internal_ip_address = google_compute_address.internal_gateway_ip.name
    }
  )
  filename = "${local.internal_gateway_manifests_directory}/gateway-internal.yaml"
}

resource "local_file" "internal_route" {
  content = templatefile(
    "${path.module}/templates/gateway/httproute-internal.tftpl.yaml",
    {
      httproute_name       = local.llmd_httproute_name_internal
      kubernetes_namespace = var.llmd_kubernetes_namespace
      gateway_name         = local.llmd_gateway_name_internal
      inferencepool_name   = local.llmd_inferencepool_name
    }
  )
  file_permission = "0644"
  filename        = "${local.internal_gateway_manifests_directory}/httproute-internal.yaml"
}

# Apply internal gateway manifests
module "kubectl_apply_int_gateway_res" {
  depends_on = [
    module.kubectl_apply_namespace,
    local_file.internal_route,
    local_file.gateway_internal_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.internal_gateway_manifests_directory
  manifest_includes_namespace = true
}
