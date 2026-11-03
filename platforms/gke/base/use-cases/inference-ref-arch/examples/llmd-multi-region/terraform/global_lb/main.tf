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

# One cross-region internal Application Load Balancer in front of the regional
# inference pools of every cluster.
#
# - Frontend: one internal forwarding rule (VIP) per region, all pointing to the
#   same global target proxy and URL map. Clients call the VIP in their region.
# - Backends: one global backend service per experiment arm. Its backends are
#   the GKE standalone zonal NEGs of that arm in every region:
#     baseline  -> the plain vLLM pods (port 8000)
#     ppcr / ob -> the llm-d router proxies (port 8081), which pick the vLLM pod
#                  with the llm-d endpoint picker (EPP)
# - Cross-region traffic distribution: a service load balancing policy
#   (WATERFALL_BY_REGION, or SPRAY_TO_REGION to spray across zones), and each
#   region's capacity in in-progress requests (balancingMode IN_FLIGHT, the
#   default) or as a request rate (balancingMode RATE).
# - The URL map default service selects the active arm, so switching arms
#   doesn't change the VIPs.

locals {
  backend_regions = {
    for name, b in var.backends : name => distinct([for neg in b.negs : neg.region])
  }
}

resource "google_project_service" "services" {
  for_each = toset([
    "compute.googleapis.com",
    "networkservices.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = var.project_id
  service                    = each.value
}

resource "google_compute_health_check" "backend" {
  for_each = var.backends
  provider = google-beta

  check_interval_sec  = 5
  healthy_threshold   = 1
  name                = "${var.name}-${each.key}"
  project             = google_project_service.services["compute.googleapis.com"].project
  timeout_sec         = 5
  unhealthy_threshold = 2

  http_health_check {
    port               = each.value.health_check_port
    port_specification = "USE_FIXED_PORT"
    request_path       = each.value.health_check_path
  }

  # Health state transitions are logged, to tell health check failover apart
  # from capacity-based spillover in the load balancer request logs.
  log_config {
    enable = true
  }
}

resource "google_network_services_service_lb_policies" "policy" {
  provider = google-beta

  description              = "Cross-region traffic distribution for ${var.name}"
  load_balancing_algorithm = var.load_balancing_algorithm
  location                 = "global"
  name                     = var.name
  project                  = google_project_service.services["networkservices.googleapis.com"].project
}

resource "google_compute_backend_service" "backend" {
  for_each = var.backends
  provider = google-beta

  health_checks         = [google_compute_health_check.backend[each.key].id]
  load_balancing_scheme = "INTERNAL_MANAGED"
  locality_lb_policy    = each.value.locality_lb_policy
  name                  = "${var.name}-${each.key}"
  project               = google_project_service.services["compute.googleapis.com"].project
  protocol              = "HTTP"
  service_lb_policy     = "//networkservices.googleapis.com/${google_network_services_service_lb_policies.policy.id}"
  timeout_sec           = var.timeout_sec

  dynamic "backend" {
    for_each = each.value.negs

    content {
      # IN_FLIGHT measures capacity in in-progress requests, which suits
      # requests that take seconds to minutes (LLM completions); it requires
      # the LONG traffic duration. RATE measures new requests per second.
      balancing_mode   = var.balancing_mode
      traffic_duration = var.balancing_mode == "IN_FLIGHT" ? "LONG" : null
      # Region capacity divided by the number of endpoints in that region
      # (computed by scripts/deploy-global-lb.sh).
      max_rate_per_endpoint               = var.balancing_mode == "RATE" ? backend.value.max_rate_per_endpoint : null
      max_in_flight_requests_per_endpoint = var.balancing_mode == "IN_FLIGHT" ? backend.value.max_in_flight_requests_per_endpoint : null
      capacity_scaler                     = 1.0
      group                               = backend.value.self_link
      preference                          = backend.value.region == var.preferred_region ? "PREFERRED" : "DEFAULT"
    }
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_url_map" "lb" {
  default_service = google_compute_backend_service.backend[var.active_backend].id
  name            = var.name
  project         = google_project_service.services["compute.googleapis.com"].project
}

resource "google_compute_target_http_proxy" "lb" {
  name    = var.name
  project = google_project_service.services["compute.googleapis.com"].project
  url_map = google_compute_url_map.lb.id
}

resource "google_compute_global_forwarding_rule" "vip" {
  for_each = var.regions

  ip_protocol           = "TCP"
  load_balancing_scheme = "INTERNAL_MANAGED"
  name                  = "${var.name}-${each.key}"
  network               = var.network
  port_range            = "80"
  project               = google_project_service.services["compute.googleapis.com"].project
  subnetwork            = each.value.subnetwork
  target                = google_compute_target_http_proxy.lb.id
}
