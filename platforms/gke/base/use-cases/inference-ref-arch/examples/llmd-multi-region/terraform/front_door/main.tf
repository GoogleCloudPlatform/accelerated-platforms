# Copyright 2026 Google LLC
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
# OPTIONAL, IAP-protected external front door for the internal multi-cluster
# Inference Gateway (prototype, for demos).
#
# This terraservice only creates the Google Cloud resources that must exist
# before the GKE Gateway (gke-l7-global-external-managed) is created in the
# config cluster:
#   - a global static external IPv4 address,
#   - a DNS-only Cloud Endpoints service: <name>.endpoints.<project>.cloud.goog,
#   - a Google-managed SSL certificate for that host name, referenced by the
#     Gateway with networking.gke.io/pre-shared-certs,
#   - an SSL policy (TLS 1.2+, RESTRICTED profile), referenced by a
#     GCPGatewayPolicy,
#   - optionally, a Cloud Armor backend security policy (source IP allowlist),
#     referenced by the GCPBackendPolicy,
#   - optionally, a project-level IAP role binding.
#
# The backend service is created by the GKE Gateway controller, so by default
# scripts/deploy-front-door.sh grants roles/iap.httpsResourceAccessor on that
# backend service only, after the Gateway is programmed (the same discovery
# approach as the llmd example: the networking.gke.io/backend-services
# annotation of the Gateway).
#
# The patterns (managed certificate, Cloud Endpoints DNS with undelete, named
# address) follow examples/llmd/initialize/external_gateway.tf.
###############################################################################

data "google_project" "this" {
  project_id = var.project_id
}

# Keep these names in sync with fd_names() in scripts/deploy-front-door.sh,
# which references them from the Kubernetes manifests.
locals {
  address_name         = "${var.name}-ip"
  ssl_certificate_name = "${var.name}-cert"
  ssl_policy_name      = "${var.name}-ssl"
  security_policy_name = "${var.name}-armor"
}

resource "google_project_service" "services" {
  for_each = toset([
    "compute.googleapis.com",
    "iap.googleapis.com",
    "servicecontrol.googleapis.com",
    "servicemanagement.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = data.google_project.this.project_id
  service                    = each.value
}

###############################################################################
# Address, DNS, and certificate
###############################################################################
resource "google_compute_global_address" "front_door" {
  depends_on = [google_project_service.services]

  address_type = "EXTERNAL"
  description  = "IAP-protected external front door for the multi-region llm-d Inference Gateway (prototype)."
  ip_version   = "IPV4"
  name         = local.address_name
  project      = data.google_project.this.project_id
}

# Deleted Cloud Endpoints services are kept for 30 days and block re-creation
# with the same name, so undelete first (no-op when the service doesn't exist
# or isn't deleted).
resource "terraform_data" "endpoint_undelete" {
  triggers_replace = [var.hostname]

  provisioner "local-exec" {
    command     = "gcloud endpoints services undelete ${var.hostname} --project=${data.google_project.this.project_id} --quiet >/dev/null 2>&1 || exit 0"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }
}

resource "google_endpoints_service" "front_door" {
  depends_on = [
    google_project_service.services,
    terraform_data.endpoint_undelete,
  ]

  openapi_config = templatefile(
    "${path.module}/templates/endpoint.tftpl.yaml",
    {
      endpoint   = var.hostname
      ip_address = google_compute_global_address.front_door.address
    }
  )
  project      = data.google_project.this.project_id
  service_name = var.hostname
}

# Provisioning starts once the host name resolves to the load balancer and the
# load balancer serves this certificate (typically 15-60 minutes).
resource "google_compute_managed_ssl_certificate" "front_door" {
  depends_on = [google_project_service.services]

  name    = local.ssl_certificate_name
  project = data.google_project.this.project_id

  managed {
    domains = [var.hostname]
  }
}

resource "google_compute_ssl_policy" "front_door" {
  depends_on = [google_project_service.services]

  min_tls_version = "TLS_1_2"
  name            = local.ssl_policy_name
  profile         = "RESTRICTED"
  project         = data.google_project.this.project_id
}

###############################################################################
# Optional Cloud Armor source IP allowlist
###############################################################################
resource "google_compute_security_policy" "front_door" {
  count = var.cloud_armor_enabled ? 1 : 0

  depends_on = [google_project_service.services]

  description = "Source IP allowlist for the llm-d multi-region front door. IAP is still enforced for allowed sources."
  name        = local.security_policy_name
  project     = data.google_project.this.project_id
  type        = "CLOUD_ARMOR"

  # A rule matches at most 10 source ranges, so the allowlist is split.
  dynamic "rule" {
    for_each = chunklist(var.cloud_armor_allowed_source_cidrs, 10)
    content {
      action      = "allow"
      description = "Allowed source ranges (${rule.key + 1})"
      priority    = 1000 + rule.key

      match {
        versioned_expr = "SRC_IPS_V1"
        config {
          src_ip_ranges = rule.value
        }
      }
    }
  }

  rule {
    action      = "deny(403)"
    description = "Deny everything else"
    priority    = 2147483647

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }

  lifecycle {
    precondition {
      condition     = length(var.cloud_armor_allowed_source_cidrs) > 0
      error_message = "cloud_armor_allowed_source_cidrs must not be empty when cloud_armor_enabled is true."
    }
  }
}

###############################################################################
# Optional project-level IAP access (broader than the default, which is the
# front door backend service only)
###############################################################################
resource "google_iap_web_iam_member" "project_level" {
  for_each = var.iap_grant_project_level ? toset(var.iap_members) : toset([])

  depends_on = [google_project_service.services]

  member  = each.value
  project = data.google_project.this.project_id
  role    = "roles/iap.httpsResourceAccessor"
}
