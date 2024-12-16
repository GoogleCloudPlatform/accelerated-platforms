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

data "google_compute_network" "main_vpc_network" {
  name    = local.network_name
  project = google_project_service.dns_googleapis_com.project
}

resource "google_compute_network_firewall_policy" "federated_learning_fw_policy" {
  name        = "federated-learning-firewall-policy"
  project     = data.google_project.default.project_id
  description = "Federated learning firewall policy"
}

resource "google_compute_network_firewall_policy_association" "federated_learning_vpc_associations" {
  name              = "federated-learning-firewall-policy-association"
  attachment_target = data.google_compute_network.main_vpc_network.id
  firewall_policy   = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  project           = data.google_project.default.project_id
}


resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_deny_all" {
  priority                = 65535
  project                 = data.google_project.default.project_id
  action                  = "deny"
  description             = "Default deny egress from node pools"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  rule_name               = "node-pools-deny-egress"
  target_service_accounts = local.list_nodepool_sa_emails

  match {
    dest_ip_ranges = ["0.0.0.0/0"]

    layer4_configs {
      ip_protocol = "all"
    }
  }
}

resource "google_compute_network_firewall_policy_rule" "federated_learning_fw_rule_allow_configsync" {
  priority                = 1000
  project                 = data.google_project.default.project_id
  action                  = "allow"
  description             = "Allow egress from node pools to Config Sync source repository"
  direction               = "EGRESS"
  enable_logging          = true
  firewall_policy         = google_compute_network_firewall_policy.federated_learning_fw_policy.name
  rule_name               = "node-pools-allow-configsync"
  target_service_accounts = local.list_nodepool_sa_emails

  match {
    dest_fqdns = var.config_management_fqdns

    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["22", "443"] # Allow both SSH and HTTPS access
    }
  }
}

# Ref: https://github.com/GoogleCloudPlatform/federated-learning/blob/89b0405eaea6b7f49b8e811fda7c981494218558/terraform/network.tf

# TODO: Allow egress from node pools to cluster nodes, pods and services
# TODO: Allow egress from node pools to the Kubernetes API server
# TODO: Allow egress from node pools to Google APIs via Private Google Access
