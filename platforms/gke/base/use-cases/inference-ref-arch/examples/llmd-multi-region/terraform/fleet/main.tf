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

# Fleet features for multi-cluster Gateways and the multi-cluster Inference
# Gateway:
# - Multi-cluster Services (MCS): ServiceExport/ServiceImport, used by the
#   plain vLLM baseline arm.
# - Multi-cluster Ingress/Gateway ("ingress" feature) with a config cluster:
#   reconciles Gateway, HTTPRoute, HealthCheckPolicy, and GCPBackendPolicy
#   resources in the config cluster, and creates GCPInferencePoolImport
#   resources for exported InferencePools.
#
# NOTE: these are fleet-wide (project-wide) settings, and a fleet has exactly
# one config cluster for multi-cluster Gateways.
#
# https://cloud.google.com/kubernetes-engine/docs/how-to/prepare-environment-multi-cluster-gateways
# https://cloud.google.com/kubernetes-engine/docs/how-to/setup-multicluster-inference-gateway

data "google_project" "fleet" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.fleet.number
}

resource "google_project_service" "services" {
  for_each = toset([
    "autoscaling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "dns.googleapis.com",
    "gkeconnect.googleapis.com",
    "gkehub.googleapis.com",
    "multiclusteringress.googleapis.com",
    "multiclusterservicediscovery.googleapis.com",
    "networkservices.googleapis.com",
    "trafficdirector.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = var.project_id
  service                    = each.value
}

resource "google_gke_hub_feature" "multiclusterservicediscovery" {
  depends_on = [google_project_service.services]

  location = "global"
  name     = "multiclusterservicediscovery"
  project  = var.project_id
}

resource "google_gke_hub_feature" "multiclusteringress" {
  depends_on = [
    google_gke_hub_feature.multiclusterservicediscovery,
    google_project_service.services,
  ]

  location = "global"
  name     = "multiclusteringress"
  project  = var.project_id

  spec {
    multiclusteringress {
      config_membership = "projects/${var.project_id}/locations/global/memberships/${var.config_membership_id}"
    }
  }
}

# MCS importer (runs in every member cluster as gke-mcs/gke-mcs-importer).
resource "google_project_iam_member" "mcs_importer_network_viewer" {
  depends_on = [google_gke_hub_feature.multiclusterservicediscovery]

  member  = "principal://iam.googleapis.com/projects/${local.project_number}/locations/global/workloadIdentityPools/${var.project_id}.svc.id.goog/subject/ns/gke-mcs/sa/gke-mcs-importer"
  project = var.project_id
  role    = "roles/compute.networkViewer"
}

resource "google_project_service_identity" "mcsd" {
  provider   = google-beta
  depends_on = [google_project_service.services]

  project = var.project_id
  service = "multiclusterservicediscovery.googleapis.com"
}

resource "google_project_iam_member" "mcsd_service_agent" {
  member  = "serviceAccount:${google_project_service_identity.mcsd.email}"
  project = var.project_id
  role    = "roles/multiclusterservicediscovery.serviceAgent"
}

resource "google_project_service_identity" "mci" {
  provider   = google-beta
  depends_on = [google_project_service.services]

  project = var.project_id
  service = "multiclusteringress.googleapis.com"
}

resource "google_project_iam_member" "mci_container_admin" {
  member  = "serviceAccount:${google_project_service_identity.mci.email}"
  project = var.project_id
  role    = "roles/container.admin"
}

# The core platform creates private clusters without a public control plane
# endpoint (kubectl uses the DNS endpoint). The multi-cluster Gateway
# controller then reaches the clusters through the Connect gateway, which
# requires this role. Without it, every membership in
# `gcloud container fleet ingress describe` reports "Lost connection" and the
# *-mc GatewayClasses are never installed in the config cluster.
resource "google_project_iam_member" "mci_gateway_admin" {
  member  = "serviceAccount:${google_project_service_identity.mci.email}"
  project = var.project_id
  role    = "roles/gkehub.gatewayAdmin"
}
