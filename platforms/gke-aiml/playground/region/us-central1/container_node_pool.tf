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

resource "google_container_node_pool" "cpu_n4s8" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster            = google_container_cluster.mlp.name
  initial_node_count = 1
  location           = var.region
  name               = "cpu-n4s8"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
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
    service_account = google_service_account.cluster.email
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
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "cpu-n4s8-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
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
    service_account = google_service_account.cluster.email
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
      node_config[0].taint,
    ]
  }

  timeouts {
    create = "30m"
    update = "20m"
  }
}



#######################################################################################################################
# GPU
# Available zones: https://cloud.google.com/compute/docs/gpus/gpu-regions-zones#view-using-table
#######################################################################################################################

###################################################################################################
# A100 x 2
###################################################################################################

resource "google_container_node_pool" "gpu_a100x2_a2h2" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x2-a2h2"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "40GB"
    }
    machine_type    = "a2-highgpu-2g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x2_a2h2_dws" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x2-a2h2-dws"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "40GB"
    }
    machine_type    = "a2-highgpu-2g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x2_a2h2_res" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x2-a2h2-res"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "40GB"
    }
    machine_type    = "a2-highgpu-2g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x2_a2h2_spot" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x2-a2h2-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "40GB"
    }
    machine_type    = "a2-highgpu-2g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    spot = true

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

###################################################################################################
# A100 x 8
###################################################################################################

resource "google_container_node_pool" "gpu_a100x8_a2h8" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x8-a2h8"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "320GB"
    }
    machine_type    = "a2-highgpu-8g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x8_a2h8_dws" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x8-a2h8-dws"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "320GB"
    }
    machine_type    = "a2-highgpu-8g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x8_a2h8_res" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x8-a2h8-res"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "320GB"
    }
    machine_type    = "a2-highgpu-8g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_a100x8_a2h8_spot" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-a100x8-a2h8-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-central1-f",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "a100"
      "resource-type" : "gpu"
      "resource-variant" : "320GB"
    }
    machine_type    = "a2-highgpu-8g"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    spot = true

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 8
      type  = "nvidia-tesla-a100"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

###################################################################################################
# H100 x 8
###################################################################################################

resource "google_container_node_pool" "gpu_h100x8_a3h8" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-h100x8-a3h8"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
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
    service_account = google_service_account.cluster.email
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
        gpu_driver_version = var.gpu_driver_version
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
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-h100x8-a3h8-dws"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
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
    service_account = google_service_account.cluster.email
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
        gpu_driver_version = var.gpu_driver_version
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
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-h100x8-a3h8-res"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
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
    service_account = google_service_account.cluster.email
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
        gpu_driver_version = var.gpu_driver_version
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
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-h100x8-a3h8-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
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
    service_account = google_service_account.cluster.email
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
        gpu_driver_version = var.gpu_driver_version
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



###################################################################################################
# L4 x 2 
###################################################################################################

resource "google_container_node_pool" "gpu_l4x2_g2s24" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-l4x2-g2s24"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "l4"
      "resource-type" : "gpu"
    }
    machine_type    = "g2-standard-24"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-l4"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_l4x2_g2s24_dws" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-l4x2-g2s24-dws"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "l4"
      "resource-type" : "gpu"
    }
    machine_type    = "g2-standard-24"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-l4"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_l4x2_g2s24_res" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-l4x2-g2s24-res"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "l4"
      "resource-type" : "gpu"
    }
    machine_type    = "g2-standard-24"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-l4"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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

resource "google_container_node_pool" "gpu_l4x2_g2s24_spot" {
  depends_on = [google_gke_hub_membership.cluster]

  # Variables
  cluster  = google_container_cluster.mlp.name
  location = var.region
  name     = "gpu-l4x2-g2s24-spot"
  node_locations = [
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
  ]
  project = data.google_project.environment.project_id

  # Blocks
  autoscaling {
    location_policy      = "ANY"
    total_max_node_count = 1000
    total_min_node_count = 0
  }

  lifecycle {
    ignore_changes = [
      node_config[0].labels,
      node_config[0].taint,
    ]
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-model" : "l4"
      "resource-type" : "gpu"
    }
    machine_type    = "g2-standard-24"
    service_account = google_service_account.cluster.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    spot = true

    # Blocks
    gcfs_config {
      enabled = true
    }

    guest_accelerator {
      count = 2
      type  = "nvidia-l4"

      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
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



#######################################################################################################################
# TPU
# Available zones: https://cloud.google.com/tpu/docs/regions-zones
#######################################################################################################################
