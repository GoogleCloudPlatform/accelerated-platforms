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
  workflow_api_endpoint       = local.workflow_api_endpoints_hostname
  workflow_api_service_name   = "workflow-api"
  workflow_api_service_port   = 8080
  gateway_manifests_directory = "${local.manifests_directory}/gateway"
  gateway_name                = "internal-https"
  network_name                = var.network_name != null ? var.network_name : local.unique_identifier_prefix
  gateway_subnetwork_name     = "gateway-subnet"
  hostname_suffix             = "endpoints.${data.google_project.cluster.project_id}.cloud.goog"
  workflow_api_serviceaccount = "workflow-api-sa"
}

data "google_client_config" "default" {}

data "google_client_openid_userinfo" "identity" {}

###############################################################################
# Setup service account for workflow-api in the namespace
###############################################################################

resource "local_file" "workflow_api_serviceaccount" {
  content = templatefile(
    "${path.module}/templates/serviceaccount.tftpl.yaml",
    {
      name      = local.workflow_api_serviceaccount
      namespace = var.comfyui_kubernetes_namespace
    }
  )
  filename = "${local.manifests_directory}/serviceaccount-${local.workflow_api_serviceaccount}.yaml"
}

module "kubectl_apply_serviceaccount" {
  depends_on = [
    local_file.workflow_api_serviceaccount,
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.manifests_directory
  manifest_includes_namespace = true
}

###############################################################################
# GATEWAY
###############################################################################
resource "google_project_service" "certificatemanager_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.cluster.project_id
  service                    = "certificatemanager.googleapis.com"
}

resource "google_certificate_manager_certificate" "internal_regional_gateway" {
  depends_on = [
    google_project_service.certificatemanager_googleapis_com,
  ]

  name      = "${local.unique_identifier_prefix}-workflow-api-internal-gateway"
  project   = data.google_project.cluster.project_id
  location  = var.cluster_region

  managed {
    domains = [
      local.workflow_api_endpoint,
      ]
    dns_authorizations = [
      google_certificate_manager_dns_authorization.test_workflow_api_internal.id,
      ]
  }
}

resource "google_certificate_manager_dns_authorization" "test_workflow_api_internal" {
  name        = "dns-auth"
  description = "DNS auth for Managed SSL Certificate"
  domain      = local.workflow_api_endpoint
  location    = var.cluster_region 
  project     = data.google_project.cluster.project_id
}

resource "google_compute_subnetwork" "gateway_subnet" {
  ip_cidr_range            = var.workflow_api_gateway_subnet_cidr_range
  name                     = local.gateway_subnetwork_name
  network                  = local.network_name
  role                     = "ACTIVE"
  project                  = data.google_project.cluster.project_id
  region                   = var.cluster_region
}

resource "google_compute_subnetwork" "proxy_subnet" {
  name                     = "gateway-proxy-subnet"
  ip_cidr_range            = var.workflow_api_proxy_subnet_cidr_range
  network                  = local.network_name
  role                     = "ACTIVE"
  project                  = data.google_project.cluster.project_id
  region                   = var.cluster_region
  purpose                  = "REGIONAL_MANAGED_PROXY"
}

resource "google_compute_address" "internal_gateway_https" {
  name         = "${local.unique_identifier_prefix}-workflow-api-internal-gateway-https"
  project      = data.google_project.cluster.project_id
  subnetwork   = google_compute_subnetwork.gateway_subnet.id
  region       = var.cluster_region
  address_type = "INTERNAL"
  purpose      = "SHARED_LOADBALANCER_VIP"
}

resource "local_file" "internal_gateway_https_yaml" {
  depends_on = [
    google_compute_address.internal_gateway_https
  ]

  content = templatefile(
    "${path.module}/templates/gateway-internal-https.tftpl.yaml",
    {
      address_name         = google_compute_address.internal_gateway_https.name
      gateway_name         = local.gateway_name
      namespace            = var.comfyui_kubernetes_namespace
      ssl_certificate_name = google_certificate_manager_certificate.internal_regional_gateway.name
      hostname             = local.workflow_api_endpoint
    }
  )
  filename = "${local.gateway_manifests_directory}/gateway-internal-https.yaml"
}

###############################################################################
# ENDPOINTS
###############################################################################
resource "terraform_data" "workflow_api_https_endpoint_undelete" {
  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${local.workflow_api_endpoint} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "workflow_api_https" {
  depends_on = [
    terraform_data.workflow_api_https_endpoint_undelete,
    google_compute_address.internal_gateway_https,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/endpoint.tftpl.yaml",
    {
      endpoint   = local.workflow_api_endpoint
      ip_address = google_compute_address.internal_gateway_https.address
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = local.workflow_api_endpoint
}

# ROUTES
###############################################################################
resource "local_file" "route_workflow_api_https_yaml" {
  content = templatefile(
    "${path.module}/templates/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name # Should match the Gateway K8s object name
      hostname        = local.workflow_api_endpoint
      http_route_name = "workflow-api-https"
      namespace       = var.comfyui_kubernetes_namespace
      service_name    = local.workflow_api_service_name
      service_port    = local.workflow_api_service_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-workflow-api-https.yaml"
}

###############################################################################
# Apply gateway resources
###############################################################################
module "kubectl_apply_gateway_res" {
  depends_on = [
    google_endpoints_service.workflow_api_https,
    local_file.internal_gateway_https_yaml,
    local_file.route_workflow_api_https_yaml,
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.gateway_manifests_directory
  manifest_includes_namespace = true
}
