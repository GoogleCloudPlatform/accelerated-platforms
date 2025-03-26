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

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_egress_to_nvflare" {
  count = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") ? 0 : 1

  action          = "allow"
  description     = "Allow egress to NVIDIA FLARE"
  direction       = "EGRESS"
  enable_logging  = true
  firewall_policy = local.federated_learning_firewall_policy_name
  priority        = 1010
  project         = data.google_project.default.project_id
  rule_name       = "${local.cluster_name}-node-pools-allow-egress-nvidia-flare"

  target_service_accounts = flatten(concat(
    local.node_pool_service_account_emails,
    [data.google_service_account.cluster.email],
  ))

  match {
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["8002", "8003"]
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_ingress_to_ingress_gateway_nvflare" {
  action          = "allow"
  description     = "Allow ingress traffic to the ingress gateway for the NVIDIA FLARE example"
  direction       = "INGRESS"
  enable_logging  = true
  firewall_policy = local.federated_learning_firewall_policy_name
  priority        = 1011
  project         = data.google_project.default.project_id
  rule_name       = "${local.cluster_name}-ingress-ingress-gateway-nvflare"

  target_service_accounts = flatten(concat(
    local.node_pool_service_account_emails,
    [data.google_service_account.cluster.email],
  ))

  match {
    src_ip_ranges = ["0.0.0.0/0"]

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["8002", "8003"]
    }
  }
}

data "google_netblock_ip_ranges" "health_checkers_netblock_ip_range" {
  range_type = "health-checkers"
}

data "google_netblock_ip_ranges" "legacy_health_checkers_netblock_ip_range" {
  range_type = "legacy-health-checkers"
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_load_balancing_health_checks_nvflare" {
  action          = "allow"
  description     = "Allow Cloud Load Balancing health checks to cluster VMs to NVFLARE EXAMPLE ports"
  direction       = "INGRESS"
  enable_logging  = true
  firewall_policy = local.federated_learning_firewall_policy_name
  priority        = 1012
  project         = data.google_project.default.project_id
  rule_name       = "${local.cluster_name}-ingress-cloud-lb-health-checks-nvflare"

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
