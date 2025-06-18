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
  gateway_subnetwork_name = "${local.unique_identifier_prefix}-gateway"
  proxy_subnetwork_name   = "${local.unique_identifier_prefix}-proxy"

  hostname_suffix = "endpoints.${data.google_project.cluster.project_id}.cloud.goog"

  gateway_manifests_directory = "${local.manifests_directory}/gateway"
  manifests_directory         = "${local.namespace_directory}/${var.comfyui_kubernetes_namespace}"
  manifests_directory_root    = "${path.module}/../../../../kubernetes/manifests"
  namespace_directory         = "${local.manifests_directory_root}/namespace"

  workflow_api_service_name   = "workflow-api"
  workflow_api_service_port   = 8080
  workflow_api_serviceaccount = "${local.unique_identifier_prefix}-workflow-api"
}

data "google_client_config" "default" {}

data "google_client_openid_userinfo" "identity" {}

data "google_compute_global_address" "external_gateway_https" {
  name    = local.comfyui_gateway_address_name
  project = data.google_project.cluster.project_id
}

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

resource "google_compute_managed_ssl_certificate" "workflow_api" {
  depends_on = [
    google_project_service.certificatemanager_googleapis_com,
  ]

  name    = "${local.unique_identifier_prefix}-${var.comfyui_kubernetes_namespace}-workflow-api"
  project = data.google_project.cluster.project_id

  managed {
    domains = [
      local.workflow_api_endpoints_hostname,
    ]
  }
}

# resource "google_certificate_manager_certificate" "internal_regional_gateway" {
#   depends_on = [
#     google_project_service.certificatemanager_googleapis_com,
#   ]

#   name      = "${local.unique_identifier_prefix}-workflow-api-internal-gateway"
#   project   = data.google_project.cluster.project_id
#   location  = var.cluster_region

#   managed {
#     domains = [
#       local.workflow_api_endpoints_hostname,
#       ]
#     dns_authorizations = [
#       google_certificate_manager_dns_authorization.test_workflow_api_internal.id,
#       ]
#   }
# }

# resource "google_certificate_manager_dns_authorization" "test_workflow_api_internal" {
#   name        = "dns-auth"
#   description = "DNS auth for Managed SSL Certificate"
#   domain      = local.workflow_api_endpoints_hostname
#   location    = var.cluster_region 
#   project     = data.google_project.cluster.project_id
# }

# resource "google_compute_subnetwork" "gateway_subnet" {
#   ip_cidr_range = var.workflow_api_subnet_gateway_cidr_range
#   name          = local.gateway_subnetwork_name
#   network       = local.networking_network_name
#   role          = "ACTIVE"
#   project       = data.google_project.cluster.project_id
#   region        = var.cluster_region
# }

# resource "google_compute_subnetwork" "proxy_subnet" {
#   name          = local.proxy_subnetwork_name
#   ip_cidr_range = var.workflow_api_subnet_proxy_cidr_range
#   network       = local.networking_network_name
#   role          = "ACTIVE"
#   project       = data.google_project.cluster.project_id
#   region        = var.cluster_region
#   purpose       = "REGIONAL_MANAGED_PROXY"
# }

# resource "google_compute_address" "internal_gateway_https" {
#   name         = "${local.unique_identifier_prefix}-workflow-api-internal-gateway-https"
#   project      = data.google_project.cluster.project_id
#   subnetwork   = google_compute_subnetwork.gateway_subnet.id
#   region       = var.cluster_region
#   address_type = "INTERNAL"
#   purpose      = "SHARED_LOADBALANCER_VIP"
# }

resource "local_file" "internal_gateway_https_yaml" {
  depends_on = [
    data.google_compute_address.external_gateway_https
  ]

  content = templatefile(
    "${path.module}/../comfyui/templates/gateway/gateway-external-https.tftpl.yaml",
    {
      address_name         = local.comfyui_gateway_address_name
      gateway_name         = local.comfyui_gateway_name
      namespace            = var.comfyui_kubernetes_namespace
      ssl_certificate_name = local.workflow_api_gateway_ssl_certificates
    }
  )
  filename = "${local.gateway_manifests_directory}/gateway-external-https.yaml"
}

###############################################################################
# ENDPOINTS
###############################################################################
resource "terraform_data" "workflow_api_https_endpoint_undelete" {
  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${local.workflow_api_endpoints_hostname} --project=${data.google_project.cluster.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "workflow_api_https" {
  depends_on = [
    terraform_data.workflow_api_https_endpoint_undelete,
    data.google_compute_address.external_gateway_https,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/endpoint.tftpl.yaml",
    {
      endpoint   = local.workflow_api_endpoints_hostname
      ip_address = data.google_compute_address.external_gateway_https.address
    }
  )
  project      = data.google_project.cluster.project_id
  service_name = local.workflow_api_endpoints_hostname
}

# ROUTES
###############################################################################
resource "local_file" "route_workflow_api_https_yaml" {
  content = templatefile(
    "${path.module}/templates/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.comfyui_gateway_name # Should match the Gateway K8s object name
      hostname        = local.workflow_api_endpoints_hostname
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
  manifest_can_be_updated     = true
  manifest_includes_namespace = true
}
