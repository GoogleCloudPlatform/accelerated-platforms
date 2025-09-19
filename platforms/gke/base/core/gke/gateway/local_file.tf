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

resource "local_file" "namespace_yaml" {
  content = templatefile(
    "${path.module}/templates/namespace.yaml",
    {
      kubernetes_namespace = local.my_kubernetes_namespace
    }
  )
  file_permission = "0644"
  filename        = local.my_kubernetes_namespace_file
}

resource "local_file" "gke_l7_global_external_managed_gateway_yaml" {
  content = templatefile(
    "${path.module}/templates/gke-l7-global-external-managed/gateway.yaml",
    {
      address_name = local.gke_l7_global_external_managed_gateway_address_name
      certificates = google_compute_managed_ssl_certificate.gke_l7_global_external_managed.name
      name         = local.gke_l7_global_external_managed_gateway_name
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/gateway-gke-l7-global-external-managed.yaml"
}

resource "local_file" "gke_l7_regional_external_managed_gateway_yaml" {
  content = templatefile(
    "${path.module}/templates/gke-l7-regional-external-managed/gateway.yaml",
    {
      address_name = local.gke_l7_regional_external_managed_gateway_address_name
      #certificates = google_compute_managed_ssl_certificate.gke_l7_regional_external_managed.name
      certificates = ""
      name         = local.gke_l7_regional_external_managed_gateway_name
      region       = local.cluster_region
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/gateway-gke-l7-${local.cluster_region}-external-managed.yaml"
}

resource "local_file" "gke_l7_rilb_gateway_yaml" {
  content = templatefile(
    "${path.module}/templates/gke-l7-rilb/gateway.yaml",
    {
      #certificates = google_compute_managed_ssl_certificate.gke_l7_rilb.name
      certificates = ""
      name         = local.gke_l7_rilb_gateway_name
      region       = local.cluster_region
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/gateway-gke-l7-${local.cluster_region}-ilb.yaml"
}

resource "local_file" "hello_world_deployment_yaml" {
  content = templatefile(
    "${path.module}/templates/hello-world/deployment.tftpl.yaml",
    {
      image = "us-docker.pkg.dev/google-samples/containers/gke/hello-app:2.0"
      name  = "hello-world"
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/deployment-hello-world.yaml"
}

resource "local_file" "hello_world_http_route_gke_l7_global_external_managed_yaml" {
  content = templatefile(
    "${path.module}/templates/hello-world/http-route.tftpl.yaml",
    {
      gateway_name = local.gke_l7_global_external_managed_gateway_name
      hostname     = local.gke_l7_global_external_managed_endpoint
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/http-route-hello-world-gke-l7-global-external-managed.yaml"
}

resource "local_file" "hello_world_http_route_gke_l7_regional_external_managed_yaml" {
  content = templatefile(
    "${path.module}/templates/hello-world/http-route.tftpl.yaml",
    {
      gateway_name = local.gke_l7_regional_external_managed_gateway_name
      hostname     = local.gke_l7_regional_external_managed_endpoint
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/http-route-hello-world-gke-l7-regional-external-managed.yaml"
}

resource "local_file" "hello_world_http_route_gke_l7_rilb_yaml" {
  content = templatefile(
    "${path.module}/templates/hello-world/http-route.tftpl.yaml",
    {
      gateway_name = local.gke_l7_rilb_gateway_name
      hostname     = local.gke_l7_rilb_endpoint
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/http-route-hello-world-gke-l7-rilb.yaml"
}
