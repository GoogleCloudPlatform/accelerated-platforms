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
  mlflow_bucket_location   = var.mlflow_bucket_location != null ? var.mlflow_bucket_location : local.cluster_region
  mlflow_bucket_name       = var.mlflow_bucket_name != null ? var.mlflow_bucket_name : "${local.mlflow_bucket_project_id}-${local.unique_identifier_prefix}-mlflow"
  mlflow_bucket_project_id = var.mlflow_bucket_project_id != null ? var.mlflow_bucket_project_id : var.platform_default_project_id
}

resource "google_storage_bucket" "mlflow" {
  for_each = toset(var.mlflow_bucket_name == null ? ["managed"] : [])

  force_destroy               = true
  location                    = local.mlflow_bucket_location
  name                        = local.mlflow_bucket_name
  project                     = local.mlflow_bucket_project_id
  uniform_bucket_level_access = true
}

data "google_storage_bucket" "mlflow" {
  depends_on = [
    google_storage_bucket.mlflow,
  ]

  name    = local.mlflow_bucket_name
  project = local.mlflow_bucket_project_id
}
