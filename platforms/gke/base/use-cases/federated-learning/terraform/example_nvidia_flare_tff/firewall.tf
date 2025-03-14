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
  nvidia_flare_tff_example_destination_fqdns = (
    startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") ?
    [
      "client1.${var.federated_learning_nvidia_flare_tff_example_domain}",
      "client2.${var.federated_learning_nvidia_flare_tff_example_domain}",
    ]
    :
    [
      "server1.${var.federated_learning_nvidia_flare_tff_example_domain}",
    ]
  )
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_egress_to_nvflare" {
  action                  = "allow"
  description             = "Allow egress to NVIDIA FLARE"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = local.federated_learning_firewall_policy_name
  priority                = 1010
  project                 = data.google_project.default.project_id
  rule_name               = "${local.cluster_name}-node-pools-allow-egress-nvidia-flare"
  target_service_accounts = local.node_pool_service_account_emails

  match {
    dest_fqdns = local.nvidia_flare_tff_example_destination_fqdns

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

  target_service_accounts = local.node_pool_service_account_emails

  match {
    src_ip_ranges = ["0.0.0.0/0"]

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["8002", "8003"]
    }
  }
}
