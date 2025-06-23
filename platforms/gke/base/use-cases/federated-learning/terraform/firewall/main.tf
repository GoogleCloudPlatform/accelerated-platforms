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

data "google_service_account" "cluster" {
  account_id = local.cluster_node_pool_service_account_id
  project    = local.cluster_node_pool_service_account_project_id
}


resource "google_compute_network_firewall_policy" "federated_learning_fw_policy" {
  description = "Federated learning firewall policy"
  name        = local.federated_learning_firewall_policy_name
  project     = data.google_project.cluster.project_id
}

resource "google_compute_network_firewall_policy_association" "federated_learning_vpc_associations" {
  name              = "${local.cluster_name}-federated-learning-firewall-policy-association"
  attachment_target = data.google_compute_network.main_vpc_network.id
  firewall_policy   = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  project           = data.google_project.cluster.project_id
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_deny_all" {
  action                  = "deny"
  description             = "Default deny egress from node pools"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority                = 65535
  project                 = data.google_project.cluster.project_id
  rule_name               = "${local.cluster_name}-node-pools-deny-egress"
  target_service_accounts = local.node_pool_service_account_emails

  match {
    dest_ip_ranges = ["0.0.0.0/0"]

    layer4_configs {
      ip_protocol = "all"
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_egress_to_cluster" {
  action                  = "allow"
  description             = "Allow egress from node pools to cluster nodes, pods and services"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority                = 1000
  project                 = data.google_project.cluster.project_id
  rule_name               = "${local.cluster_name}-node-pools-allow-egress-nodes-pods-services"
  target_service_accounts = local.node_pool_service_account_emails

  match {
    dest_ip_ranges = concat(
      local.cluster_subnetwork_secondary_ip_ranges,
      [data.google_container_cluster.cluster.services_ipv4_cidr]
    )

    layer4_configs {
      ip_protocol = "all"
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_egress_to_k8s_api" {
  action                  = "allow"
  description             = "Allow egress from node pools to the Kubernetes API server"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority                = 1001
  project                 = data.google_project.cluster.project_id
  rule_name               = "${local.cluster_name}-node-pools-allow-egress-api-server"
  target_service_accounts = local.node_pool_service_account_emails

  match {
    dest_ip_ranges = [local.master_ipv4_cidr_block]

    layer4_configs {
      ip_protocol = "tcp"
      ports       = [443, 10250]
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_egress_to_private_google_access" {
  action                  = "allow"
  description             = "Allow egress from node pools to Google APIs via Private Google Access"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority                = 1002
  project                 = data.google_project.cluster.project_id
  rule_name               = "${local.cluster_name}-node-pools-allow-egress-api-server"
  target_service_accounts = local.node_pool_service_account_emails

  match {
    dest_ip_ranges = data.google_netblock_ip_ranges.private_google_access_netblock_ip_range.cidr_blocks_ipv4

    layer4_configs {
      ip_protocol = "tcp"
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_intra_egress" {
  action          = "allow"
  description     = "Allow pods to communicate with each other and the control plane"
  direction       = "EGRESS"
  enable_logging  = true
  firewall_policy = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority        = 1003
  project         = data.google_project.cluster.project_id
  rule_name       = "${local.cluster_name}-intra-cluster-egress"

  target_service_accounts = concat(
    local.node_pool_service_account_emails,
  )

  match {
    dest_ip_ranges = compact(
      concat(
        [
          local.master_ipv4_cidr_block,
          data.google_compute_subnetwork.region.ip_cidr_range,
          data.google_container_cluster.cluster.tpu_ipv4_cidr_block,
        ],
        local.cluster_subnetwork_secondary_ip_ranges
      )
    )

    layer4_configs {
      ip_protocol = "all"
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_control_plane_ingress" {
  action          = "allow"
  description     = "Allow control plane to connect to pods for admission controllers and webhooks"
  direction       = "INGRESS"
  enable_logging  = true
  firewall_policy = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority        = 1004
  project         = data.google_project.cluster.project_id
  rule_name       = "${local.cluster_name}-control-plane-ingress-webhooks"

  target_service_accounts = local.node_pool_service_account_emails

  match {
    src_ip_ranges = [local.master_ipv4_cidr_block]

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["8443", "9443", "15017"]
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_ingress_to_ingress_gateway" {
  action          = "allow"
  description     = "Allow ingress traffic to the ingress gateway"
  direction       = "INGRESS"
  enable_logging  = true
  firewall_policy = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority        = 1006
  project         = data.google_project.cluster.project_id
  rule_name       = "${local.cluster_name}-ingress-ingress-gateway"

  target_service_accounts = local.node_pool_service_account_emails

  match {
    src_ip_ranges = ["0.0.0.0/0"]

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["80", "443"]
    }
  }
}

data "google_netblock_ip_ranges" "health_checkers_netblock_ip_range" {
  range_type = "health-checkers"
}

data "google_netblock_ip_ranges" "legacy_health_checkers_netblock_ip_range" {
  range_type = "legacy-health-checkers"
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_load_balancing_health_checks" {
  action          = "allow"
  description     = "Allow Cloud Load Balancing health checks to cluster VMs"
  direction       = "INGRESS"
  enable_logging  = true
  firewall_policy = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  priority        = 1007
  project         = data.google_project.cluster.project_id
  rule_name       = "${local.cluster_name}-ingress-cloud-lb-health-checks"

  target_service_accounts = flatten(concat(
    local.node_pool_service_account_emails,
    [data.google_service_account.cluster.email],
  ))

  match {
    src_ip_ranges = concat(
      data.google_netblock_ip_ranges.health_checkers_netblock_ip_range.cidr_blocks_ipv4,
      data.google_netblock_ip_ranges.legacy_health_checkers_netblock_ip_range.cidr_blocks_ipv4,
    )

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["0-65535"]
    }
  }
}
