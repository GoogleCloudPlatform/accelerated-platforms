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
  backend_files = [
    abspath("${path.module}/backend.tf.bucket"),
    abspath("${path.module}/../container_cluster/backend.tf"),
    abspath("${path.module}/../container_node_pool/backend.tf"),
    abspath("${path.module}/../gke_enterprise/configmanagement/git/backend.tf"),
    abspath("${path.module}/../gke_enterprise/configmanagement/oci/backend.tf"),
    abspath("${path.module}/../gke_enterprise/fleet_membership/backend.tf"),
    abspath("${path.module}/../gke_enterprise/servicemesh/backend.tf"),
    abspath("${path.module}/../networking/backend.tf"),
    abspath("${path.module}/../workloads/kueue/backend.tf"),
  ]
  container_node_pool_folder = abspath("${path.module}/../container_node_pool")
}

data "google_project" "default" {
  project_id = var.cluster_project_id
}

resource "google_storage_bucket" "terraform" {
  for_each = toset(var.create_terraform_bucket ? ["create"] : [])

  force_destroy               = false
  location                    = var.cluster_region
  name                        = local.terraform_bucket_name
  project                     = data.google_project.default.project_id
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

data "google_storage_bucket" "terraform" {
  depends_on = [google_storage_bucket.terraform]

  name    = local.terraform_bucket_name
  project = data.google_project.default.project_id
}

resource "null_resource" "configure_nodepools_for_region" {
  provisioner "local-exec" {
    command = <<EOT
cd ${local.container_node_pool_folder} && \
rm -f container_node_pool_*.tf && \
ln -s cpu/region/${var.cluster_region}/container_node_pool_*.tf ./
ln -s gpu/region/${var.cluster_region}/container_node_pool_*.tf ./
ln -s tpu/region/${var.cluster_region}/container_node_pool_*.tf ./
EOT
  }

  triggers = {
    always_run = timestamp()
  }
}

resource "null_resource" "write_storage_bucket" {
  for_each = toset(local.backend_files)

  provisioner "local-exec" {
    command     = <<EOT
echo "Writing 'bucket' changes to '${self.triggers.backend_file}'" && \
sed -i 's/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 ${jsonencode(data.google_storage_bucket.terraform.name)}/' ${self.triggers.backend_file}
    EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    when        = destroy
    command     = <<EOT
echo "Reverting 'bucket' changes in '${self.triggers.backend_file}'" && \
sed -i 's/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 ""/' ${self.triggers.backend_file}
    EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  triggers = {
    backend_file = each.value
    md5          = data.google_storage_bucket.terraform.name
  }
}
