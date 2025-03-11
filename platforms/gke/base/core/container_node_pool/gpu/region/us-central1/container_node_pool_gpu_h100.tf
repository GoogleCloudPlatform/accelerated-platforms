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
# GPU
# Available zones: https://cloud.google.com/compute/docs/gpus/gpu-regions-zones#view-using-table
#######################################################################################################################

###################################################################################################
# H100 x 8
###################################################################################################

resource "google_container_node_pool" "gpu_h100x8_a3h8" {
  # Variables
  cluster  = data.google_container_cluster.cluster.name
  location = var.cluster_region
  name     = "gpu-h100x8-a3h8"
  node_locations = [
    "us-central1-a",
    "us-central1-c"
  ]
  project = data.google_project.default.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "h100"
      "resource-type" : "gpu"
    }
    machine_type    = "a3-highgpu-8g"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    ephemeral_storage_local_ssd_config {
      local_ssd_count = 16
    }

    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-h100-80gb"

      gpu_driver_installation_config {
        gpu_driver_version = var.cluster_gpu_driver_version
      }
    }

    gvnic {
      enabled = true
    }

    reservation_affinity {
      consume_reservation_type = "NO_RESERVATION"
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

  timeouts {
    create = "30m"
    update = "20m"
  }
}

###############################################################################

resource "google_container_node_pool" "gpu_h100x8_a3h8_dws" {
  # Variables
  cluster  = data.google_container_cluster.cluster.name
  location = var.cluster_region
  name     = "gpu-h100x8-a3h8-dws"
  node_locations = [
    "us-central1-a",
    "us-central1-c"
  ]
  project = data.google_project.default.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "h100"
      "resource-type" : "gpu"
    }
    machine_type    = "a3-highgpu-8g"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    ephemeral_storage_local_ssd_config {
      local_ssd_count = 16
    }

    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-h100-80gb"

      gpu_driver_installation_config {
        gpu_driver_version = var.cluster_gpu_driver_version
      }
    }

    gvnic {
      enabled = true
    }

    reservation_affinity {
      consume_reservation_type = "NO_RESERVATION"
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

  queued_provisioning {
    enabled = true
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}

###############################################################################

resource "google_container_node_pool" "gpu_h100x8_a3h8_res" {
  # Variables
  cluster  = data.google_container_cluster.cluster.name
  location = var.cluster_region
  name     = "gpu-h100x8-a3h8-res"
  node_locations = [
    "us-central1-a",
    "us-central1-c"
  ]
  project = data.google_project.default.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "h100"
      "resource-type" : "gpu"
    }
    machine_type    = "a3-highgpu-8g"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    ephemeral_storage_local_ssd_config {
      local_ssd_count = 16
    }

    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-h100-80gb"

      gpu_driver_installation_config {
        gpu_driver_version = var.cluster_gpu_driver_version
      }
    }

    gvnic {
      enabled = true
    }

    reservation_affinity {
      consume_reservation_type = "ANY_RESERVATION"
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }

    taint {
      effect = "NO_SCHEDULE"
      key    = "reservation"
      value  = true
    }
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}

###############################################################################

resource "google_container_node_pool" "gpu_h100x8_a3h8_spot" {
  # Variables
  cluster  = data.google_container_cluster.cluster.name
  location = var.cluster_region
  name     = "gpu-h100x8-a3h8-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-c"
  ]
  project = data.google_project.default.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].resource_labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "h100"
      "resource-type" : "gpu"
    }
    machine_type    = "a3-highgpu-8g"
    service_account = data.google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    spot = true

    # Blocks
    ephemeral_storage_local_ssd_config {
      local_ssd_count = 16
    }

    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-h100-80gb"

      gpu_driver_installation_config {
        gpu_driver_version = var.cluster_gpu_driver_version
      }
    }

    gvnic {
      enabled = true
    }

    reservation_affinity {
      consume_reservation_type = "NO_RESERVATION"
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

  timeouts {
    create = "30m"
    update = "20m"
  }
}
