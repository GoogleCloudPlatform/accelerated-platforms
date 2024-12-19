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

resource "google_container_cluster" "cluster" {
  provider = google-beta

  datapath_provider        = "ADVANCED_DATAPATH"
  deletion_protection      = false
  enable_shielded_nodes    = true
  location                 = var.cluster_region
  name                     = local.cluster_name
  network                  = local.network_name
  project                  = google_project_service.container_googleapis_com.project
  remove_default_node_pool = false
  subnetwork               = local.subnetwork_name

  addons_config {
    gcp_filestore_csi_driver_config {
      enabled = true
    }

    gcs_fuse_csi_driver_config {
      enabled = true
    }

    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
  }

  cluster_autoscaling {
    autoscaling_profile = "OPTIMIZE_UTILIZATION"
    enabled             = true

    auto_provisioning_defaults {
      disk_type = "pd-balanced"
      oauth_scopes = [
        "https://www.googleapis.com/auth/cloud-platform"
      ]
      service_account = google_service_account.cluster.email

      management {
        auto_repair  = true
        auto_upgrade = true
      }

      shielded_instance_config {
        enable_integrity_monitoring = true
        enable_secure_boot          = true
      }

      upgrade_settings {
        max_surge       = 0
        max_unavailable = 1
        strategy        = "SURGE"
      }
    }

    resource_limits {
      resource_type = "cpu"
      minimum       = 4
      maximum       = 1024
    }

    resource_limits {
      resource_type = "memory"
      minimum       = 16
      maximum       = 4096
    }

    resource_limits {
      resource_type = "nvidia-a100-80gb"
      maximum       = 32
    }

    resource_limits {
      resource_type = "nvidia-l4"
      maximum       = 32
    }

    resource_limits {
      resource_type = "nvidia-tesla-t4"
      maximum       = 256
    }

    resource_limits {
      resource_type = "nvidia-tesla-a100"
      maximum       = 64
    }

    resource_limits {
      resource_type = "nvidia-tesla-k80"
      maximum       = 32
    }

    resource_limits {
      resource_type = "nvidia-tesla-p4"
      maximum       = 32
    }

    resource_limits {
      resource_type = "nvidia-tesla-p100"
      maximum       = 32
    }

    resource_limits {
      resource_type = "nvidia-tesla-v100"
      maximum       = 32
    }
  }

  binary_authorization {
    evaluation_mode = var.cluster_binary_authorization_evaluation_mode
  }

  confidential_nodes {
    enabled = var.cluster_confidential_nodes_enabled
  }

  cost_management_config {
    enabled = true
  }

  dynamic "database_encryption" {
    for_each = var.cluster_database_encryption_state == "ENCRYPTED" ? ["database_encryption"] : []
    content {
      state    = var.cluster_database_encryption_state
      key_name = var.cluster_database_encryption_key_name
    }
  }

  gateway_api_config {
    channel = var.cluster_gateway_api_config_channel
  }

  ip_allocation_policy {
  }

  lifecycle {
    ignore_changes = [
      node_pool
    ]
  }

  logging_config {
    enable_components = [
      "APISERVER",
      "CONTROLLER_MANAGER",
      "SCHEDULER",
      "SYSTEM_COMPONENTS",
      "WORKLOADS"
    ]
  }

  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled = !var.cluster_enable_private_endpoint
    cidr_blocks {
      cidr_block   = var.subnet_cidr_range
      display_name = "vpc-cidr"
    }
  }

  monitoring_config {
    advanced_datapath_observability_config {
      enable_metrics = true
      enable_relay   = false
    }

    enable_components = [
      "APISERVER",
      "CADVISOR",
      "CONTROLLER_MANAGER",
      "DAEMONSET",
      "DCGM",
      "DEPLOYMENT",
      "HPA",
      "KUBELET",
      "POD",
      "SCHEDULER",
      "STATEFULSET",
      "STORAGE",
      "SYSTEM_COMPONENTS"
    ]

    managed_prometheus {
      enabled = true
    }
  }

  node_pool {
    initial_node_count = 1
    name               = "system"

    autoscaling {
      location_policy      = "BALANCED"
      total_max_node_count = 32
      total_min_node_count = 1
    }

    network_config {
      enable_private_nodes = true
    }

    node_config {
      machine_type    = "e2-standard-4"
      service_account = google_service_account.cluster.email
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
  }

  node_pool_defaults {
    node_config_defaults {
      gcfs_config {
        enabled = true
      }
    }
  }

  private_cluster_config {
    enable_private_nodes        = true
    enable_private_endpoint     = var.cluster_enable_private_endpoint
    master_ipv4_cidr_block      = var.cluster_master_ipv4_cidr_block
    private_endpoint_subnetwork = var.cluster_private_endpoint_subnetwork

    master_global_access_config {
      enabled = var.cluster_master_global_access_enabled
    }
  }

  release_channel {
    channel = "RAPID"
  }

  secret_manager_config {
    enabled = true
  }

  security_posture_config {
    mode               = "BASIC"
    vulnerability_mode = "VULNERABILITY_ENTERPRISE"
  }

  workload_identity_config {
    workload_pool = "${data.google_project.cluster.project_id}.svc.id.goog"
  }
}

data "google_container_cluster" "default" {
  depends_on = [google_container_cluster.cluster]

  location = var.cluster_region
  name     = local.cluster_name
  project  = var.cluster_project_id
}
