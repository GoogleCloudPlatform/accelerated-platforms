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
  comfyui_endpoint              = "comfyui.${var.comfyui_kubernetes_namespace}.${var.platform_name}.${local.hostname_suffix}"
  comfyui_port                  = 8848
  comfyui_service_name          = "comfyui-svc"
  gateway_manifests_directory   = "${local.manifests_directory}/gateway"
  gateway_name                  = "external-https"
  hostname_suffix               = "endpoints.${data.google_project.default.project_id}.cloud.goog"
  iap_domain                    = var.iap_domain != null ? var.iap_domain : split("@", trimspace(data.google_client_openid_userinfo.identity.email))[1]
  iap_oath_brand                = "projects/${data.google_project.default.number}/brands/${data.google_project.default.number}"
  kubeconfig_directory          = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file               = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  manifests_directory           = "${local.manifests_directory_root}/namespace/${var.comfyui_kubernetes_namespace}"
  namespace_directory           = "${local.manifests_directory_root}/namespace"
  namespace_manifests_directory = "${local.manifests_directory}/namespace"
  serviceaccount                = "${var.comfyui_kubernetes_namespace}-sa"
}

data "google_client_config" "default" {}

data "google_client_openid_userinfo" "identity" {}

###############################################################################
# Create Namespace
###############################################################################

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "terraform_data" "namespace" {
  input = {
    manifests_dir = local.namespace_directory
    namespace     = var.comfyui_kubernetes_namespace
    app_name      = var.app_name
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p ${self.input.manifests_dir} && \
cp -r templates/namespace/namespace-comfyui.tftpl.yaml ${self.input.manifests_dir}/namespace-comfyui.yaml
sed -i "s/\$${namespace}/${self.input.namespace}/; s/\$${app}/${self.input.app_name}/"  ${self.input.manifests_dir}/namespace-comfyui.yaml
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers_replace = {
    manifests_dir         = local.namespace_directory
    namespace             = var.comfyui_kubernetes_namespace
    app_name              = var.app_name
    template_content_hash = filemd5("${path.module}/templates/namespace/namespace-comfyui.tftpl.yaml")

  }
}

module "kubectl_apply_namespace" {
  depends_on = [
    terraform_data.namespace,
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file = data.local_file.kubeconfig.filename
  #manifest                    = "${local.namespace_directory}/namespace-comfyui.yaml"
  manifest                    = local.namespace_directory
  manifest_includes_namespace = true
}

###############################################################################
# Setup service account and network policies in the namespace
###############################################################################

resource "local_file" "serviceaccount" {
  content = templatefile(
    "${path.module}/templates/namespace/serviceaccount.tftpl.yaml",
    {
      serviceaccount = local.serviceaccount,
      namespace      = var.comfyui_kubernetes_namespace,

    }
  )
  filename = "${local.namespace_manifests_directory}/serviceaccount.yaml"
}

resource "local_file" "network_policy" {
  content = templatefile(
    "${path.module}/templates/namespace/network-policy.tftpl.yaml",
    {
      namespace = var.comfyui_kubernetes_namespace,
      name      = var.comfyui_kubernetes_namespace,

    }
  )
  filename = "${local.namespace_manifests_directory}/network-policy.yaml"
}

module "kubectl_apply_namespace_setup" {
  depends_on = [
    terraform_data.namespace,
    module.kubectl_apply_namespace,
    local_file.serviceaccount,
    local_file.network_policy,
    #local_file.iap_oauth_k8s_secret
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.namespace_manifests_directory
  manifest_includes_namespace = true
}

###############################################################################
# GATEWAY
###############################################################################
resource "google_project_service" "certificatemanager_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.default.project_id
  service                    = "certificatemanager.googleapis.com"
}

resource "google_compute_managed_ssl_certificate" "external_gateway" {
  depends_on = [
    google_project_service.certificatemanager_googleapis_com,
  ]

  name    = "${var.platform_name}-${var.comfyui_kubernetes_namespace}-external-gateway"
  project = data.google_project.default.project_id

  managed {
    domains = [
      local.comfyui_endpoint,
    ]
  }
}

resource "google_compute_global_address" "external_gateway_https" {
  name    = "${var.platform_name}-comfyui-external-gateway-https"
  project = data.google_project.default.project_id
}

resource "local_file" "gateway_external_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/gateway-external-https.tftpl.yaml",
    {
      address_name         = google_compute_global_address.external_gateway_https.name,
      namespace            = var.comfyui_kubernetes_namespace,
      gateway_name         = local.gateway_name,
      ssl_certificate_name = google_compute_managed_ssl_certificate.external_gateway.name
    }
  )
  filename   = "${local.gateway_manifests_directory}/gateway-external-https.yaml"
  depends_on = [google_compute_global_address.external_gateway_https]
}

# ENDPOINTS
###############################################################################
resource "google_endpoints_service" "comfyui_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.comfyui_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.default.project_id
  service_name = local.comfyui_endpoint
}

# ROUTES
###############################################################################
resource "local_file" "route_comfyui_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      namespace       = var.comfyui_kubernetes_namespace,
      http_route_name = "comfyui-https",
      hostname        = local.comfyui_endpoint
      service_name    = local.comfyui_service_name
      service_port    = local.comfyui_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-comfyui-https.yaml"
}

###############################################################################
# IAP
###############################################################################
resource "google_project_service" "iap_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.default.project_id
  service                    = "iap.googleapis.com"
}

# TODO: Look at adding validation that the OAuth brand exists
resource "google_iap_client" "comfyui_client" {
  depends_on = [
    google_project_service.iap_googleapis_com
  ]

  brand        = local.iap_oath_brand
  display_name = "IAP-gkegw-${var.platform_name}-${var.comfyui_kubernetes_namespace}-comfyui-dashboard"
}

resource "google_iap_web_iam_member" "domain_iap_https_resource_accessor" {
  depends_on = [
    #google_project_service.iap_googleapis_com,
    local_file.gateway_external_https_yaml
  ]

  project = data.google_project.default.project_id
  member  = "domain:${local.iap_domain}"
  role    = "roles/iap.httpsResourceAccessor"
}

###############################################################################
# IAP Policy
###############################################################################
resource "kubernetes_secret_v1" "comfyui_oauth" {
  data = {
    secret = google_iap_client.comfyui_client.secret
  }

  metadata {
    name      = "comfyui-oauth"
    namespace = var.comfyui_kubernetes_namespace
  }
  depends_on = [module.kubectl_apply_namespace]
}

resource "local_file" "policy_iap_comfyui_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/gcp-backend-policy-iap-service.tftpl.yaml",
    {
      oauth_client_id          = google_iap_client.comfyui_client.client_id
      oauth_client_secret_name = "comfyui-oauth"
      policy_name              = "comfyui"
      service_name             = local.comfyui_service_name
      namespace                = var.comfyui_kubernetes_namespace
    }
  )
  filename   = "${local.gateway_manifests_directory}/policy-iap-comfyui.yaml"
  depends_on = [module.kubectl_apply_namespace_setup]
}

###############################################################################
# Apply gateway resources
###############################################################################
module "kubectl_apply_gateway_res" {
  depends_on = [
    terraform_data.namespace,
    module.kubectl_apply_namespace_setup,
    local_file.gateway_external_https_yaml,
    local_file.route_comfyui_https_yaml,
    local_file.policy_iap_comfyui_yaml,
    kubernetes_secret_v1.comfyui_oauth,
    google_endpoints_service.comfyui_https
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.gateway_manifests_directory
  manifest_includes_namespace = true
}
