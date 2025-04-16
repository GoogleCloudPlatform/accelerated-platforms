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
  cloud_storage_service_path                    = "${path.module}/../cloud_storage"
  cloud_storage_service_configuration_file_path = "${local.cloud_storage_service_path}/_inference-ref-arch-cloud-storage.auto.tfvars"
}

resource "local_file" "cloud_storage_terraform_configuration_file" {
  count = var.ira_use_case_flavor == "ira-online-gpu" ? 1 : 0

  content = <<-EOT
  ira_cloud_storage_buckets = {
    "ira-model" = {
      force_destroy      = true,
      versioning_enabled = false
    }
  }

  ira_cloud_storage_buckets_iam_bindings = [
    {
      bucket_name = "ira-model",
      member      = "${var.ira_kubernetes_namespace}/sa/${var.ira_use_case_flavor}-ksa",
      role        = "roles/storage.objectUser"
    }
  ]
  EOT

  file_permission = "0644"
  filename        = local.cloud_storage_service_configuration_file_path
}
