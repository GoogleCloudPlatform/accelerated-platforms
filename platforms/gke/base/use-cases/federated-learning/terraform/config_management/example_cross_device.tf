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
  federated_learning_cross_device_example_templates_directory_path = "${local.config_management_templates_directory_path}/cross-device-example"

  federated_learning_cross_device_example_templates_to_render = flatten([
    for tenant in local.tenants : [
      # {
      #   destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_workloads.yaml"
      #   template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_workloads.yaml"
      #   template_variables = merge(
      #     tenant.kubernetes_templates_configuration_values,
      #     {
      #       cross_device_workload_name = "taskassignment"
      #     },
      #   )
      # },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_gateway.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_gateway.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            ip_address_name = ""
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_mesh.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_mesh.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_telemetry.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_telemetry.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_authorization_policies.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_authorization_policies.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_network_policies.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_network_policies.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskassignment_destination_rules.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_destination_rules.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskassignment"
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskmanagement_destination_rules.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_destination_rules.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskmanagement"
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskscheduler_destination_rules.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_destination_rules.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskscheduler"
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskassignment_virtual_services.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_virtual_services.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskassignment",
            cross_device_workload_port = 8083
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskmanagement_virtual_services.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_virtual_services.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskmanagement",
            cross_device_workload_port = 8082
          },
        )
      },
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/cross_device_taskscheduler_virtual_services.yaml"
        template_source_file_path = "${local.federated_learning_cross_device_example_templates_directory_path}/cross_device_virtual_services.yaml"
        template_variables = merge(
          tenant.kubernetes_templates_configuration_values,
          {
            cross_device_workload_name = "taskscheduler",
            cross_device_workload_port = 8082
          },
        )
      },
    ]
  ])
}