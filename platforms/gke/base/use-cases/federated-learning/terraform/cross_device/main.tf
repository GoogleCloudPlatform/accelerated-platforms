# Copyright 2023 Google LLC
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
  tenant = "${var.namespace}-sync"
  cross_device_workloads = [{
    name = "taskassignment"
    port = 8083
    }, {
    name = "taskmanagement"
    port = 8082
    }, {
    name = "taskscheduler"
    port = 8082
    }
  ]
}

resource "local_file" "gateway" {
  content = templatefile(
    "${path.module}/templates/cross_device_gateway.yaml",
    {
      namespace_name = var.namespace
      ip_address_name = google_compute_address.default.name
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_gateway.yaml"
}

resource "local_file" "mesh" {
  content = templatefile(
    "${path.module}/templates/cross_device_mesh.yaml",
    {
      namespace_name = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_mesh.yaml"
}

resource "local_file" "telemetry" {
  content = templatefile(
    "${path.module}/templates/cross_device_telemetry.yaml",
    {
      namespace_name = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_telemetry.yaml"
}

resource "local_file" "authorization_policies" {
  content = templatefile(
    "${path.module}/templates/cross_device_authorization_policies.yaml",
    {
      namespace_name = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_authorization_policies.yaml"
}

resource "local_file" "network_policies" {
  content = templatefile(
    "${path.module}/templates/cross_device_network_policies.yaml",
    {
      namespace_name = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_network_policies.yaml"
}

resource "local_file" "destination_rules" {
  for_each = {
    for workload in local.cross_device_workloads : workload.name => workload
  }
  content = templatefile(
    "${path.module}/templates/cross_device_destination_rules.yaml",
    {
      cross_device_workload_name = each.key
      namespace_name             = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_${each.key}_destination_rule.yaml"
}

resource "local_file" "virtual_services" {
  for_each = {
    for workload in local.cross_device_workloads : workload.name => workload
  }
  content = templatefile(
    "${path.module}/templates/cross_device_virtual_services.yaml",
    {
      cross_device_workload_name = each.key
      cross_device_workload_port = each.value.port
      namespace_name             = var.namespace
    }
  )
  filename = "${var.acm_config_sync_tenants_configuration_destination_directory_path}/${local.tenant}/cross_device_${each.key}_virtual_service.yaml"
}
