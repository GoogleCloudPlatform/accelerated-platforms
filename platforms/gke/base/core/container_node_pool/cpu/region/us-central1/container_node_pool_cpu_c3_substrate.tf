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

#######################################################################################################################
# Agent Substrate Worker Node Pool (Uniform C3 x 4)
# Note: Agent Substrate requires a uniform CPU microarchitecture across worker nodes so gVisor checkpoint/restore
# snapshots can migrate cleanly across nodes in the pool.
#######################################################################################################################

resource "google_container_node_pool" "cpu_c3s4_substrate" {
  cluster            = data.google_container_cluster.cluster.name
  initial_node_count = 0
  location           = local.cluster_region
  name               = "cpu-c3s4-substrate"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.cluster.project_id

  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 8
    total_min_node_count = 2
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    labels = {
      "ate.dev/worker-pool" : "true"
      "resource-model" : "c3"
      "resource-type" : "cpu"
    }
    machine_type    = "c3-standard-4"
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

  lifecycle {
    ignore_changes = [
      initial_node_count,
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}

#######################################################################################################################
# GKE Sandbox (gVisor) Node Pool for Cold-Start Baseline Comparison
#######################################################################################################################

resource "google_container_node_pool" "cpu_n4s4_gvisor" {
  provider = google-beta

  cluster            = data.google_container_cluster.cluster.name
  initial_node_count = 0
  location           = local.cluster_region
  name               = "cpu-n4s4-gvisor"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.cluster.project_id

  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 4
    total_min_node_count = 1
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    image_type = "COS_CONTAINERD"
    labels = {
      "resource-model" : "e2"
      "resource-type" : "cpu"
      "sandbox-runtime" : "gvisor"
    }
    machine_type    = "e2-standard-4"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    gcfs_config {
      enabled = true
    }

    sandbox_config {
      sandbox_type = "gvisor"
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }
  }

  lifecycle {
    ignore_changes = [
      initial_node_count,
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}
