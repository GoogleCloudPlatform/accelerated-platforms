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

resource "google_container_node_pool" "fl_container_node_pool" {
  for_each = local.tenants

  cluster            = data.google_container_cluster.cluster.name
  initial_node_count = 1
  location           = var.cluster_region
  name               = each.value.tenant_nodepool_name
  project            = data.google_project.cluster.project_id

  autoscaling {
    location_policy      = "BALANCED"
    total_max_node_count = 32
    total_min_node_count = 1
  }

  network_config {
    enable_private_nodes = true
  }

  node_config {
    enable_confidential_storage = var.cluster_confidential_nodes_enabled
    machine_type                = var.federated_learning_node_pool_machine_type
    service_account             = each.value.tenant_nodepool_sa_email

    labels = {
      "federated-learning-tenant" : each.value.tenant_name
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    confidential_nodes {
      enabled = var.cluster_confidential_nodes_enabled
    }

    gcfs_config {
      enabled = true
    }

    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }

    taint {
      effect = "NO_EXECUTE"
      key    = "federated-learning-tenant"
      value  = each.value.tenant_name
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
