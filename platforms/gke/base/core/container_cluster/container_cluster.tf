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

locals {
  kubeconfig_directory = "${path.module}/../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
}

data "google_compute_zones" "region" {
  project = data.google_project.cluster.project_id
  region  = local.cluster_region
}

resource "google_container_cluster" "cluster" {
  depends_on = [
    google_project_iam_member.cluster_sa
  ]

  provider = google-beta

  datapath_provider        = "ADVANCED_DATAPATH"
  deletion_protection      = false
  enable_shielded_nodes    = true
  location                 = local.cluster_region
  name                     = local.cluster_name
  network                  = local.network_cluster_network_name
  node_locations           = data.google_compute_zones.region.names
  project                  = google_project_service.cluster["container.googleapis.com"].project
  remove_default_node_pool = true
  subnetwork               = local.network_cluster_subnet_node_name

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

    horizontal_pod_autoscaling {
      disabled = false
    }

    # Disabled until b/431744489 is fixed.
    parallelstore_csi_driver_config {
      enabled = false
    }
  }

  cluster_autoscaling {
    autoscaling_profile = "OPTIMIZE_UTILIZATION"
    enabled             = var.cluster_node_auto_provisioning_enabled

    dynamic "auto_provisioning_defaults" {
      for_each = var.cluster_node_auto_provisioning_enabled ? ["auto_provisioning_defaults"] : []
      content {
        disk_type = "pd-balanced"
        oauth_scopes = [
          "https://www.googleapis.com/auth/cloud-platform"
        ]
        service_account = data.google_service_account.cluster.email

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
    }

    dynamic "resource_limits" {
      for_each = local.cluster_node_auto_provisioning_resource_limits
      content {
        maximum       = resource_limits.value.maximum
        minimum       = resource_limits.value.minimum
        resource_type = resource_limits.value.resource_type
      }
    }
  }

  binary_authorization {
    evaluation_mode = var.cluster_binary_authorization_evaluation_mode
  }

  confidential_nodes {
    enabled = var.cluster_confidential_nodes_enabled
  }

  control_plane_endpoints_config {
    dns_endpoint_config {
      allow_external_traffic = true
    }
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

  dns_config {
    cluster_dns       = "CLOUD_DNS"
    cluster_dns_scope = "CLUSTER_SCOPE"
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
      "KCP_HPA",
      "SCHEDULER",
      "SYSTEM_COMPONENTS",
      "WORKLOADS"
    ]
  }

  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled = !var.cluster_enable_private_endpoint
    cidr_blocks {
      cidr_block   = var.network_cluster_subnet_node_ip_cidr_range
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
      "JOBSET",
      "KUBELET",
      "POD",
      "SCHEDULER",
      "STATEFULSET",
      "STORAGE",
      "SYSTEM_COMPONENTS"
    ]

    managed_prometheus {
      enabled = true

      auto_monitoring_config {
        scope = var.cluster_auto_monitoring_config_scope
      }
    }
  }

  node_pool {
    initial_node_count = 0
    name               = "default-pool"

    node_config {
      machine_type    = var.cluster_system_node_pool_machine_type
      service_account = data.google_service_account.cluster.email

      oauth_scopes = [
        "https://www.googleapis.com/auth/cloud-platform"
      ]

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

  pod_autoscaling {
    hpa_profile = "PERFORMANCE"
  }

  private_cluster_config {
    enable_private_nodes        = true
    enable_private_endpoint     = var.cluster_enable_private_endpoint
    master_ipv4_cidr_block      = var.network_cluster_subnet_master_ipv4_cidr_block
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

resource "google_container_node_pool" "system" {
  # Variables
  cluster            = google_container_cluster.cluster.name
  initial_node_count = 1
  location           = local.cluster_region
  name               = "system"
  project            = google_container_cluster.cluster.project

  # Blocks
  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 1000
    total_min_node_count = 2
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    # Variables
    labels = {
      "resource-type" : "system"
    }
    machine_type    = var.cluster_system_node_pool_machine_type
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
      key    = "components.gke.io/gke-managed-components"
      value  = "true"
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

resource "terraform_data" "cluster_credentials" {
  depends_on = [
    google_container_cluster.cluster,
    google_container_node_pool.system,
  ]

  input = {
    cluster_credentials_command = local.cluster_credentials_command
    kubeconfig_file             = local.kubeconfig_file
  }

  provisioner "local-exec" {
    command     = <<EOT
mkdir -p $(dirname ${self.input.kubeconfig_file})
KUBECONFIG=${self.input.kubeconfig_file} ${self.input.cluster_credentials_command} 
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "rm -rf ${self.input.kubeconfig_file}"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    always_run = timestamp()
  }
}
