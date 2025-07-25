# Copyright 2025 Google LLC
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
  federated_learning_example                                       = "cross-device"
  federated_learning_cross_device_example_templates_directory_path = "${path.module}/templates"
  cloud_service_mesh_templates_directory_path                      = "${path.module}/../cloud_service_mesh/templates"

  additional_config_files_destination_directory_path = "${path.module}/../config_management/files/additional"
  namespace_configuration_destination_directory_path = "${local.additional_config_files_destination_directory_path}/namespace_configuration"

  federated_learning_cross_device_example_templates_to_render = flatten(concat([
    for tenant in local.tenants : [
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_gateway.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_gateway.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            federated_learning_example = local.federated_learning_example,
            ip_address_name            = "${local.unique_identifier_prefix}-cdn-ip",
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_authorization_policies.yaml"
        template_source_file_path = "${local.cloud_service_mesh_templates_directory_path}/cloud_service_mesh_authorization_policies.yaml.tftpl"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            federated_learning_example       = local.federated_learning_example,
            federated_learning_example_ports = sort(distinct([for workload in var.federated_learning_cross_device_example_workloads : "${workload.port}"]))
          }
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_network_policies.yaml"
        template_source_file_path = "${local.cloud_service_mesh_templates_directory_path}/cloud_service_mesh_network_policies.yaml.tftpl"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            federated_learning_example       = local.federated_learning_example,
            federated_learning_example_ports = sort(distinct([for workload in var.federated_learning_cross_device_example_workloads : "${workload.port}"]))
          }
        )
      }
    ]
    ], [
    for tenant in local.tenants : [
      for key, workload in var.federated_learning_cross_device_example_workloads : [
        {
          destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_${replace(key, "-", "_")}_workload.yaml"
          template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_workloads.yaml"
          template_variables = merge(
            tenant.kubernetes_templates_configuration_values,
            {
              federated_learning_example         = local.federated_learning_example,
              cross_device_workload_name         = key
              cross_device_workload_replicas     = workload.replicas
              cross_device_workload_port         = workload.port
              cross_device_workload_min_replicas = workload.min_replicas
              cross_device_workload_max_replicas = workload.max_replicas
              cross_device_image                 = data.google_artifact_registry_docker_image.workload_image[key].self_link
            },
          )
        },
        {
          destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_${replace(key, "-", "_")}_destination_rule.yaml"
          template_source_file_path = "${local.cloud_service_mesh_templates_directory_path}/cloud_service_mesh_destination_rules.yaml.tftpl"
          template_variables = merge(
            tenant.kubernetes_templates_configuration_values,
            {
              federated_learning_example       = local.federated_learning_example,
              federated_learning_workload_name = key
            },
          )
        },
        {
          destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_${replace(key, "-", "_")}_virtual_service.yaml"
          template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_virtual_services.yaml"
          template_variables = merge(
            tenant.kubernetes_templates_configuration_values,
            {
              federated_learning_example = local.federated_learning_example,
              cross_device_workload_name = key,
              cross_device_workload_port = workload.port
            },
          )
        }
      ]
    ]
  ]))
}

resource "local_file" "cross_device_example_templates_to_render" {
  for_each = {
    for template_to_render in local.federated_learning_cross_device_example_templates_to_render : template_to_render.destination_file_path => template_to_render
  }

  content = templatefile(
    each.value.template_source_file_path,
    each.value.template_variables
  )
  file_permission = "0644"
  filename        = each.value.destination_file_path
}
