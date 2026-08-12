# Copyright 2026 Google LLC
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
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory      = "${local.manifests_directory_root}/cluster/storage_class"
  manifests_directory_root = "${path.module}/../../../kubernetes/manifests"

  storage_class_rwx_name = var.storage_class_rwx_name != null ? var.storage_class_rwx_name : "${local.unique_identifier_prefix}-rwx"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "storage_class_rwx" {
  content = templatefile(
    "${path.module}/templates/manifests/storage-class-rwx.yaml.tftpl",
    {
      filestore_tier     = var.storage_class_rwx_filestore_tier
      is_default_class   = var.storage_class_rwx_default
      network_name       = local.network_cluster_network_name
      storage_class_name = local.storage_class_rwx_name
    }
  )
  filename = "${local.manifests_directory}/storage-class-rwx.yaml"
}

# A cluster can only have one default StorageClass. GKE marks 'standard-rwo'
# (Persistent Disk) as the default, which cannot provision ReadWriteMany volumes,
# so it has to give up the annotation before the Filestore class claims it.
resource "terraform_data" "remove_default_from_standard_rwo" {
  count = var.storage_class_rwx_default ? 1 : 0

  provisioner "local-exec" {
    command     = "kubectl --kubeconfig '${data.local_file.kubeconfig.filename}' annotate storageclass standard-rwo storageclass.kubernetes.io/is-default-class=false --overwrite"
    interpreter = ["bash", "-c"]
  }

  triggers_replace = {
    storage_class_rwx_name = local.storage_class_rwx_name
  }
}

module "kubectl_apply_manifests" {
  depends_on = [
    google_project_service.file_googleapis_com,
    local_file.storage_class_rwx,
    terraform_data.remove_default_from_standard_rwo,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.manifests_directory
  manifest_includes_namespace = true
  recursive                   = true
  use_kustomize               = false
}
