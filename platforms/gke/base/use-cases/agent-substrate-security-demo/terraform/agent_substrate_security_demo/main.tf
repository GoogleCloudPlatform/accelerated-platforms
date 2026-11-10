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

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "google_compute_zones" "region" {
  project = data.google_project.cluster.project_id
  region  = local.cluster_region
  status  = "UP"
}

data "google_container_cluster" "cluster" {
  location = local.cluster_region
  name     = local.cluster_name
  project  = data.google_project.cluster.project_id
}

data "google_service_account" "cluster" {
  account_id = "vm-${local.cluster_name}"
  project    = data.google_project.cluster.project_id
}

locals {
  worker_zones = try(length(local.agent_substrate_node_locations), 0) > 0 ? local.agent_substrate_node_locations : slice([
    for zone in data.google_compute_zones.region.names : zone
    if !can(regex("-ai", zone))
  ], 0, 2)

  cluster_master_parts = split(".", split("-", data.google_container_cluster.cluster.master_version)[0])
  min_gke_parts        = split(".", local.agent_substrate_min_gke_version)
  gke_version_ok = (
    tonumber(local.cluster_master_parts[0]) > tonumber(local.min_gke_parts[0]) ||
    (
      tonumber(local.cluster_master_parts[0]) == tonumber(local.min_gke_parts[0]) &&
      tonumber(local.cluster_master_parts[1]) >= tonumber(local.min_gke_parts[1])
    )
  )

  wi_subject_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
}

resource "google_container_node_pool" "agent_substrate_workers" {
  cluster            = data.google_container_cluster.cluster.name
  initial_node_count = 1
  location           = local.cluster_region
  name               = "agent-substrate-${split("-", local.agent_substrate_node_machine_type)[0]}"
  node_locations     = local.worker_zones
  project            = data.google_project.cluster.project_id
  version            = data.google_container_cluster.cluster.master_version

  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 6
    total_min_node_count = 2
  }

  lifecycle {
    ignore_changes = [
      initial_node_count,
    ]
    precondition {
      condition     = local.gke_version_ok
      error_message = "Agent Substrate requires GKE control plane and worker nodes >= ${local.agent_substrate_min_gke_version} (for native PodCertificateRequest and ClusterTrustBundle); found ${data.google_container_cluster.cluster.master_version}."
    }
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    disk_size_gb = 100
    disk_type    = local.agent_substrate_node_disk_type
    image_type   = "COS_CONTAINERD"
    labels = {
      "resource-model" : split("-", local.agent_substrate_node_machine_type)[0]
      "resource-type" : "cpu"
      "workload" : "agent-substrate"
    }
    machine_type    = local.agent_substrate_node_machine_type
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    gcfs_config {
      enabled = true
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }

    taint {
      effect = "NO_SCHEDULE"
      key    = "ate.dev/sandboxClass"
      value  = "gvisor"
    }
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}

resource "google_project_service" "agent_substrate" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudtrace.googleapis.com",
    "iamcredentials.googleapis.com",
    "monitoring.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = local.agent_substrate_project_id
  service                    = each.key
}

resource "google_artifact_registry_repository" "agent_substrate_app" {
  depends_on = [
    google_project_service.agent_substrate,
  ]

  description   = "Container image repository for Agent Substrate Security Demo actors and gateway"
  format        = "DOCKER"
  location      = local.cluster_region
  project       = local.agent_substrate_project_id
  repository_id = local.agent_substrate_ar_repository_name
}

resource "google_artifact_registry_repository_iam_member" "cluster_nodes_reader" {
  location   = google_artifact_registry_repository.agent_substrate_app.location
  member     = "serviceAccount:${data.google_service_account.cluster.email}"
  project    = google_artifact_registry_repository.agent_substrate_app.project
  repository = google_artifact_registry_repository.agent_substrate_app.name
  role       = "roles/artifactregistry.reader"
}

resource "google_storage_bucket" "ate_snapshots" {
  location = local.cluster_region
  name     = local.agent_substrate_snapshot_bucket_name
  project  = local.agent_substrate_project_id

  force_destroy               = local.agent_substrate_snapshot_bucket_force_destroy
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 7
    }
  }

  lifecycle_rule {
    action {
      type = "AbortIncompleteMultipartUpload"
    }
    condition {
      age = 1
    }
  }
}

resource "google_service_account" "ate_snapshot_transfer" {
  account_id   = local.agent_substrate_snapshot_transfer_gsa_name
  display_name = "Agent Substrate Snapshot Transfer GSA"
  project      = local.agent_substrate_project_id
}

resource "google_storage_bucket_iam_member" "ate_snapshot_transfer_admin" {
  bucket = google_storage_bucket.ate_snapshots.name
  member = "serviceAccount:${google_service_account.ate_snapshot_transfer.email}"
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "ate_snapshot_transfer_viewer" {
  bucket = google_storage_bucket.ate_snapshots.name
  member = "serviceAccount:${google_service_account.ate_snapshot_transfer.email}"
  role   = "roles/storage.bucketViewer"
}

resource "google_storage_bucket_iam_member" "ate_apiserver_snapshot_admin" {
  bucket = google_storage_bucket.ate_snapshots.name
  member = "${local.wi_subject_prefix}/ns/ate-system/sa/ate-api-server"
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "ate_apiserver_snapshot_viewer" {
  bucket = google_storage_bucket.ate_snapshots.name
  member = "${local.wi_subject_prefix}/ns/ate-system/sa/ate-api-server"
  role   = "roles/storage.bucketViewer"
}

resource "google_service_account_iam_member" "ate_apiserver_token_creator" {
  depends_on = [
    google_project_service.agent_substrate,
  ]

  member             = "${local.wi_subject_prefix}/ns/ate-system/sa/ate-api-server"
  role               = "roles/iam.serviceAccountTokenCreator"
  service_account_id = google_service_account.ate_snapshot_transfer.name
}

resource "google_project_iam_member" "gateway_aiplatform_user" {
  depends_on = [
    google_project_service.agent_substrate,
  ]

  member  = "${local.wi_subject_prefix}/ns/${local.agent_substrate_workload_namespace}/sa/gateway"
  project = local.agent_substrate_project_id
  role    = "roles/aiplatform.user"
}

resource "google_project_iam_member" "prometheus_ui_monitoring_viewer" {
  depends_on = [
    google_project_service.agent_substrate,
  ]

  member  = "${local.wi_subject_prefix}/ns/${local.agent_substrate_workload_namespace}/sa/prometheus-ui"
  project = local.agent_substrate_project_id
  role    = "roles/monitoring.viewer"
}
