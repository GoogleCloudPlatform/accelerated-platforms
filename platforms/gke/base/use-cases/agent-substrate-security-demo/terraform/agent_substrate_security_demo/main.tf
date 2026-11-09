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

data "google_container_cluster" "cluster" {
  location = local.cluster_region
  name     = local.cluster_name
  project  = data.google_project.cluster.project_id
}

data "google_service_account" "cluster" {
  account_id = "vm-${local.cluster_name}"
  project    = data.google_project.cluster.project_id
}

resource "google_container_node_pool" "agent_substrate_workers" {
  cluster            = data.google_container_cluster.cluster.name
  initial_node_count = 1
  location           = local.cluster_region
  name               = "agent-substrate-${split("-", local.agent_substrate_node_machine_type)[0]}"
  project            = data.google_project.cluster.project_id

  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 6
    total_min_node_count = 2
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
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}

resource "google_storage_bucket" "ate_snapshots" {
  name     = local.agent_substrate_snapshot_bucket_name
  project  = local.agent_substrate_project_id
  location = local.cluster_region

  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_service_account" "ate_snapshot_transfer" {
  account_id   = "ate-snapshot-transfer"
  display_name = "Agent Substrate Snapshot Transfer GSA"
  project      = local.agent_substrate_project_id
}

resource "google_storage_bucket_iam_member" "ate_snapshot_transfer_admin" {
  bucket = google_storage_bucket.ate_snapshots.name
  member = "serviceAccount:${google_service_account.ate_snapshot_transfer.email}"
  role   = "roles/storage.objectAdmin"
}
