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

#######################################################################################################################
# CPU
# Available zones: https://cloud.google.com/compute/docs/regions-zones#available
#######################################################################################################################

###################################################################################################
# N4 x 8
###################################################################################################

resource "google_container_node_pool" "cpu_n4s8" {
  # Variables
  cluster            = google_container_cluster.mlp.name
  initial_node_count = 1
  location           = local.cluster_region
  name               = "cpu-n4s8"
  node_locations = [
    "us-east4-a",
    "us-east4-b",
    "us-east4-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 32
    total_min_node_count = 1
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "n4"
      "resource-type" : "cpu"
    }
    machine_type    = "n4-standard-8"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }

    taint {
      effect = "NO_SCHEDULE"
      key    = "on-demand"
      value  = true
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

###############################################################################

resource "google_container_node_pool" "cpu_n4s8_spot" {
  # Variables
  cluster  = google_container_cluster.mlp.name
  location = local.cluster_region
  name     = "cpu-n4s8-spot"
  node_locations = [
    "us-east4-a",
    "us-east4-b",
    "us-east4-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 32
    total_min_node_count = 0
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "n4"
      "resource-type" : "cpu"
    }
    machine_type    = "n4-standard-8"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    spot = true

    # Blocks
    gcfs_config {
      enabled = true
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }

    taint {
      effect = "NO_SCHEDULE"
      key    = "spot"
      value  = true
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
