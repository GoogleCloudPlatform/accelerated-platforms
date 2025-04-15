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
  federated_learning_nvidia_flare_tff_example_templates_base_directory_path      = "${path.module}/templates"
  federated_learning_nvidia_flare_tff_example_templates_directory_path           = "${local.federated_learning_nvidia_flare_tff_example_templates_base_directory_path}/nvidia-flare-tff-example"
  federated_learning_nvidia_flare_tff_example_workspace_templates_directory_path = "${local.federated_learning_nvidia_flare_tff_example_templates_base_directory_path}/nvidia-flare-workspace"

  federated_learning_nvidia_flare_tff_example_workload_template_path          = "${local.federated_learning_nvidia_flare_tff_example_templates_directory_path}/nvidia_flare_tff_example_workload.yaml"
  federated_learning_nvidia_flare_tff_example_workspace_project_template_path = "${local.federated_learning_nvidia_flare_tff_example_workspace_templates_directory_path}/project.yml"

  additional_config_files_destination_directory_path = "${path.module}/../config_management/files/additional"
  namespace_configuration_destination_directory_path = "${local.additional_config_files_destination_directory_path}/namespace_configuration"
  nvflare_workspace_destination_directory_path       = "${path.module}/nvflare-workspace"

  # Default to the first tenant if no tenant is specified
  federated_learning_nvidia_flare_tff_example_tenant_name = var.federated_learning_nvidia_flare_tff_example_tenant_name == "" ? var.federated_learning_tenant_names[0] : var.federated_learning_nvidia_flare_tff_example_tenant_name

  namespace_configuration_template_files_suffix = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") ? "server" : "client"
  namespace_configuration_template_files        = flatten([for _, file in flatten(fileset(local.federated_learning_nvidia_flare_tff_example_templates_directory_path, "**/*${local.namespace_configuration_template_files_suffix}.yaml")) : "${local.federated_learning_nvidia_flare_tff_example_templates_directory_path}/${file}"])

  federated_learning_nvidia_flare_tff_example_templates_variables = merge(
    local.tenants[local.federated_learning_nvidia_flare_tff_example_tenant_name].kubernetes_templates_configuration_values,
    {
      federated_learning_nvidia_flare_tff_example_bucket_name                  = var.federated_learning_nvidia_flare_tff_example_bucket_name
      federated_learning_nvidia_flare_tff_example_container_image_tag          = var.federated_learning_nvidia_flare_tff_example_container_image_tag
      federated_learning_nvidia_flare_tff_example_localized_container_image_id = var.federated_learning_nvidia_flare_tff_example_localized_container_image_id
      nvidia_flare_tff_example_config_file_name                                = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") ? "fed_server.json" : "fed_client.json"
      nvidia_flare_tff_example_python_module_name                              = startswith(var.federated_learning_nvidia_flare_tff_example_workload_to_deploy, "server") ? "nvflare.private.fed.app.server.server_train" : "nvflare.private.fed.app.client.client_train"
      nvidia_flare_tff_example_workload_name                                   = var.federated_learning_nvidia_flare_tff_example_workload_to_deploy
      nvidia_flare_tff_example_site_name                                       = var.federated_learning_nvidia_flare_tff_example_workload_to_deploy
    },
  )

  federated_learning_nvidia_flare_tff_example_templates_to_render = flatten(
    concat(
      [
        {
          destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${var.federated_learning_nvidia_flare_tff_example_tenant_name}/${basename(local.federated_learning_nvidia_flare_tff_example_workload_template_path)}"
          template_source_file_path = local.federated_learning_nvidia_flare_tff_example_workload_template_path
          template_variables        = local.federated_learning_nvidia_flare_tff_example_templates_variables
        }
      ],
      [
        for template_file in local.namespace_configuration_template_files : {
          destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${var.federated_learning_nvidia_flare_tff_example_tenant_name}/${basename(template_file)}"
          template_source_file_path = "${template_file}"
          template_variables        = local.federated_learning_nvidia_flare_tff_example_templates_variables
        }
      ],
      [
        {
          destination_file_path     = "${local.nvflare_workspace_destination_directory_path}/${basename(local.federated_learning_nvidia_flare_tff_example_workspace_project_template_path)}"
          template_source_file_path = local.federated_learning_nvidia_flare_tff_example_workspace_project_template_path
          template_variables        = local.federated_learning_nvidia_flare_tff_example_templates_variables
        }
      ],
    )
  )
}

resource "local_file" "nvflare_example_templates_to_render" {
  for_each = {
    for template_to_render in local.federated_learning_nvidia_flare_tff_example_templates_to_render : template_to_render.destination_file_path => template_to_render
  }

  content = templatefile(
    each.value.template_source_file_path,
    each.value.template_variables
  )
  file_permission = "0644"
  filename        = each.value.destination_file_path
}
