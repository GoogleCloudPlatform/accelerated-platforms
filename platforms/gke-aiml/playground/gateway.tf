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

locals {
  hostname_suffix             = "endpoints.${data.google_project.environment.project_id}.cloud.goog"
  gateway_manifests_directory = "${path.module}/manifests/${var.environment_name}/${var.namespace}/gateway"
  gateway_name                = "external-https"
  iap_domain                  = var.iap_domain != null ? var.iap_domain : split("@", trimspace(data.google_client_openid_userinfo.identity.email))[1]
  iap_oath_brand              = "projects/${data.google_project.environment.number}/brands/${data.google_project.environment.number}"

  # Endpoints
  gradio_service_name = "gradio-svc"
  gradio_endpoint     = "gradio.${local.model_ops_namespace}.mlp-${var.environment_name}.${local.hostname_suffix}"
  gradio_port         = 8080

  locust_service_name = "locust-master-web-svc"
  locust_endpoint     = "locust.${local.model_ops_namespace}.mlp-${var.environment_name}.${local.hostname_suffix}"
  locust_port         = 8089

  mlflow_tracking_endpoint     = "mlflow-tracking.${data.kubernetes_namespace_v1.team.metadata[0].name}.mlp-${var.environment_name}.${local.hostname_suffix}"
  mlflow_tracking_service_name = "mlflow-tracking-svc"
  mlflow_tracking_port         = 5000

  rag_frontend_endpoint     = "rag-frontend.${data.kubernetes_namespace_v1.team.metadata[0].name}.mlp-${var.environment_name}.${local.hostname_suffix}"
  rag_frontend_port         = 8080
  rag_frontend_service_name = "rag-frontend"

  ray_head_service_name  = "ray-cluster-kuberay-head-svc"
  ray_dashboard_endpoint = "ray-dashboard.${data.kubernetes_namespace_v1.team.metadata[0].name}.mlp-${var.environment_name}.${local.hostname_suffix}"
  ray_dashboard_port     = 8265
}

###############################################################################
# GATEWAY
###############################################################################
resource "google_project_service" "certificatemanager_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.environment.project_id
  service                    = "certificatemanager.googleapis.com"
}

resource "google_compute_managed_ssl_certificate" "external_gateway" {
  depends_on = [
    google_project_service.certificatemanager_googleapis_com,
  ]

  name    = "${var.environment_name}-${var.namespace}-external-gateway"
  project = data.google_project.environment.project_id

  managed {
    domains = [
      local.gradio_endpoint,
      local.locust_endpoint,
      local.mlflow_tracking_endpoint,
      local.rag_frontend_endpoint,
      local.ray_dashboard_endpoint,
    ]
  }
}

resource "google_compute_global_address" "external_gateway_https" {
  depends_on = [
    google_project_service.compute_googleapis_com
  ]

  name    = "${var.environment_name}-${data.kubernetes_namespace_v1.team.metadata[0].name}-external-gateway-https"
  project = data.google_project.environment.project_id
}

resource "local_file" "gateway_external_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/gateway-external-https.tftpl.yaml",
    {
      address_name         = google_compute_global_address.external_gateway_https.name,
      gateway_name         = local.gateway_name,
      ssl_certificate_name = google_compute_managed_ssl_certificate.external_gateway.name
    }
  )
  filename = "${local.gateway_manifests_directory}/gateway-external-https.yaml"
}

# ENDPOINTS
###############################################################################
resource "google_endpoints_service" "gradio_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.gradio_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.environment.project_id
  service_name = local.gradio_endpoint
}

resource "google_endpoints_service" "locust_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.locust_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.environment.project_id
  service_name = local.locust_endpoint
}

resource "google_endpoints_service" "mlflow_tracking_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.mlflow_tracking_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.environment.project_id
  service_name = local.mlflow_tracking_endpoint
}

resource "google_endpoints_service" "rag_frontend_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.rag_frontend_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.environment.project_id
  service_name = local.rag_frontend_endpoint
}

resource "google_endpoints_service" "ray_dashboard_https" {
  openapi_config = templatefile(
    "${path.module}/templates/openapi/endpoint.tftpl.yaml",
    {
      endpoint   = local.ray_dashboard_endpoint,
      ip_address = google_compute_global_address.external_gateway_https.address
    }
  )
  project      = data.google_project.environment.project_id
  service_name = local.ray_dashboard_endpoint
}

# ROUTES
###############################################################################
resource "local_file" "route_gradio_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      http_route_name = "gradio-https",
      hostname        = local.gradio_endpoint
      service_name    = local.gradio_service_name
      service_port    = local.gradio_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-gradio-https.yaml"
}

resource "local_file" "route_locust_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      http_route_name = "locust-https",
      hostname        = local.locust_endpoint
      service_name    = local.locust_service_name
      service_port    = local.locust_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-locust-https.yaml"
}

resource "local_file" "route_mlflow_tracking_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      http_route_name = "mlflow-tracking-https",
      hostname        = local.mlflow_tracking_endpoint
      service_name    = local.mlflow_tracking_service_name
      service_port    = local.mlflow_tracking_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-mlflow-tracking-https.yaml"
}

resource "local_file" "route_rag_frontend_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      http_route_name = "rag-frontend-https",
      hostname        = local.rag_frontend_endpoint
      service_name    = local.rag_frontend_service_name
      service_port    = local.rag_frontend_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-rag-frontend-https_yaml"
}

resource "local_file" "route_ray_dashboard_https_yaml" {
  content = templatefile(
    "${path.module}/templates/gateway/http-route-service.tftpl.yaml",
    {
      gateway_name    = local.gateway_name,
      http_route_name = "ray-dashboard-https",
      hostname        = local.ray_dashboard_endpoint
      service_name    = local.ray_head_service_name
      service_port    = local.ray_dashboard_port
    }
  )
  filename = "${local.gateway_manifests_directory}/route-ray-dashboard-https.yaml"
}

###############################################################################
# IAP
###############################################################################
resource "google_project_service" "iap_googleapis_com" {
  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.environment.project_id
  service                    = "iap.googleapis.com"
}

# TODO: Look at adding validation that the OAuth brand exists
resource "google_iap_client" "ray_head_client" {
  depends_on = [
    google_project_service.iap_googleapis_com
  ]

  brand        = local.iap_oath_brand
  display_name = "IAP-gkegw-${var.environment_name}-${data.kubernetes_namespace_v1.team.metadata[0].name}-ray-head-dashboard"
}

# TODO: Look at possibly converting to google_iap_web_backend_service_iam_member, but would need the gateway to be created first.
# BACKEND_SERVICE=$(gcloud compute backend-services list --filter="name~'<backend-service>'" --format="value(name)")
resource "google_iap_web_iam_member" "domain_iap_https_resource_accessor" {
  depends_on = [
    google_project_service.iap_googleapis_com,
    null_resource.gateway_manifests
  ]

  project = data.google_project.environment.project_id
  member  = "domain:${local.iap_domain}"
  role    = "roles/iap.httpsResourceAccessor"
}
