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
  push_container_image_script_path = "${path.module}/scripts/build-push-container-image.sh"

  config_management_files_path                    = "${path.module}/files"
  config_management_common_files_path             = "${local.config_management_files_path}/common"
  config_management_oci_descriptors_path          = "${local.config_management_files_path}/oci_descriptors"
  config_management_templates_directory_path      = "${path.module}/templates"
  namespace_configuration_template_directory_path = "${local.config_management_templates_directory_path}/namespace_configuration"

  config_management_destination_directory_path                 = "${local.config_management_files_path}/config_management"
  config_management_common_files_destination_directory_path    = "${local.config_management_destination_directory_path}/common"
  config_management_oci_descriptors_destination_directory_path = local.config_management_destination_directory_path
  namespace_configuration_destination_directory_path           = "${local.config_management_destination_directory_path}/namespace_configuration"

  config_management_common_files          = flatten([for _, file in flatten(fileset(local.config_management_common_files_path, "**")) : file])
  config_management_oci_descriptors_files = flatten([for _, file in flatten(fileset(local.config_management_oci_descriptors_path, "**")) : file])

  namespace_configuration_template_files = flatten([for _, file in flatten(fileset(local.namespace_configuration_template_directory_path, "**")) : "${local.namespace_configuration_template_directory_path}/${file}"])

  namespaces_configuration = flatten([
    for tenant in local.tenants : concat([
      for template_file in local.namespace_configuration_template_files : {
        destination_file_path     = "${local.namespace_configuration_destination_directory_path}/${tenant.tenant_name}/${basename(template_file)}"
        template_source_file_path = "${template_file}"
        template_variables        = tenant.kubernetes_templates_configuration_values
      }
      ],
      # Add templates to render to namespace configuration in case the user
      # enabled any examples to deploy
      local.examples_templates_to_render,
    )
  ])
}

resource "local_file" "common_configuration" {
  for_each = toset(local.config_management_common_files)

  content         = file("${local.config_management_common_files_path}/${each.value}")
  file_permission = "0644"
  filename        = "${local.config_management_common_files_destination_directory_path}/${each.value}"
}

resource "local_file" "oci_descriptors_configuration" {
  for_each = toset(local.config_management_oci_descriptors_files)

  content         = file("${local.config_management_oci_descriptors_path}/${each.value}")
  file_permission = "0644"
  filename        = "${local.config_management_oci_descriptors_destination_directory_path}/${each.value}"
}

resource "local_file" "namespace_configuration" {
  for_each = {
    for namespace_config in local.namespaces_configuration : namespace_config.destination_file_path => namespace_config
  }

  content = templatefile(
    each.value.template_source_file_path,
    each.value.template_variables
  )
  file_permission = "0644"
  filename        = each.value.destination_file_path
}

resource "terraform_data" "config_management_oci_archive_push" {

  provisioner "local-exec" {
    command = local.push_container_image_script_path

    environment = {
      CONTAINER_IMAGE_BUILD_CONTEXT_PATH = local.config_management_destination_directory_path
      CONTAINER_IMAGE_REPOSITORY_DOMAIN  = local.oci_repo_domain
      CONTAINER_IMAGE_REPOSITORY_URL     = local.oci_repo_url
      CONTAINER_IMAGE_DESTINATION_TAG    = local.oci_sync_repo_url
    }
  }

  triggers_replace = [
    # Trigger whenever the contents of source directories or template configuration values change.
    # Don't depend on destination directory content because it might change between plan and apply.
    sha512(join("", [for f in fileset(local.config_management_templates_directory_path, "**") : filesha512("${local.config_management_templates_directory_path}/${f}")])),
    sha512(join("", [for f in fileset(local.config_management_common_files_path, "**") : filesha512("${local.config_management_common_files_path}/${f}")])),
    sha512(join("", [for f in fileset(local.config_management_oci_descriptors_path, "**") : filesha512("${local.config_management_oci_descriptors_path}/${f}")])),
    # Trigger whenever the namespace configuration changes
    local.namespaces_configuration,
    # Trigger whenever the contents of the container image push script changes
    filesha512(local.push_container_image_script_path),
    # Trigger whenever destination paths change
    local.config_management_destination_directory_path,
    local.config_management_common_files_destination_directory_path,
    local.config_management_oci_descriptors_destination_directory_path,
    local.namespace_configuration_destination_directory_path,
    # Trigger whenever OCI container image repository coordinates change
    local.oci_repo_domain,
    local.oci_repo_url,
    local.oci_sync_repo_url,
  ]

  # Wait for files to be there before attempting to build the OCI container image containing
  # configuration files
  depends_on = [
    local_file.common_configuration,
    local_file.oci_descriptors_configuration,
    local_file.namespace_configuration,
  ]
}
