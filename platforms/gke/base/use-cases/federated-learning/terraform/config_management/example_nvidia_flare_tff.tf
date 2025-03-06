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
  federated_learning_nvidia_flare_tff_example_templates_directory_path = "${local.config_management_templates_directory_path}/nvidia-flare-tff-example"

  # Default to the first tenant if no tenant is specified
  federated_learning_nvidia_flare_tff_example_tenant_name = var.federated_learning_nvidia_flare_tff_example_tenant_name == "" ? var.federated_learning_tenant_names[0] : var.federated_learning_nvidia_flare_tff_example_tenant_name

  federated_learning_nvidia_flare_tff_example_templates_to_render = flatten([
    for workload_name in var.federated_learning_nvidia_flare_tff_example_workloads_to_deploy : [
      {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${var.federated_learning_nvidia_flare_tff_example_tenant_name}/${workload_name}.yaml"
        template_source_file_path = "${local.federated_learning_nvidia_flare_tff_example_templates_directory_path}/nvidia_flare_tff_example_workload.yaml"
        template_variables = merge(
          local.tenants[local.federated_learning_nvidia_flare_tff_example_tenant_name].kubernetes_templates_configuration_values,
          {
            federated_learning_nvidia_flare_tff_example_bucket_name                  = var.federated_learning_nvidia_flare_tff_example_bucket_name
            federated_learning_nvidia_flare_tff_example_container_image_tag          = var.federated_learning_nvidia_flare_tff_example_container_image_tag
            federated_learning_nvidia_flare_tff_example_localized_container_image_id = var.federated_learning_nvidia_flare_tff_example_localized_container_image_id
            nvidia_flare_tff_example_config_file_name                                = startswith(workload_name, "server") ? "fed_server.json" : "fed_client.json"
            nvidia_flare_tff_example_python_module_name                              = startswith(workload_name, "server") ? "nvflare.private.fed.app.server.server_train" : "nvflare.private.fed.app.client.client_train"
            nvidia_flare_tff_example_workload_name                                   = workload_name
            nvidia_flare_tff_example_site_name                                       = startswith(workload_name, "server") ? workload_name : "site-${trimprefix(workload_name, "client")}"
          },
        )
      }
    ]
  ])
}
