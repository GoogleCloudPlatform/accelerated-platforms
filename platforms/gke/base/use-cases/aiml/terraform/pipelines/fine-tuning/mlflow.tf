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

resource "google_storage_bucket_iam_member" "data_bucket_mlflow_storage_object_admin" {
  bucket = google_storage_bucket.data.name
  member = "${local.wi_member_principal_prefix}/${local.fine_tuning_kubernetes_service_accounts["mlflow"].service_account_name}"
  role   = "roles/storage.objectAdmin"
}

resource "local_file" "mlflow_manifest" {
  content = templatefile(
    "${path.module}/templates/mlflow/manifests.tftpl.yaml",
    {
      bucket_name          = google_storage_bucket.data.name,
      service_account_name = local.fine_tuning_kubernetes_service_accounts["mlflow"].service_account_name,
    }
  )
  filename = "${local.fine_tuning_manifests_directory}/namespace/${var.fine_tuning_team_namespace}/mlflow.yaml"
}

module "kubectl_apply_mlflow_manifest" {
  depends_on = [
    module.kubectl_apply_namespace_manifest,
  ]

  source = "../../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.mlflow_manifest.filename
  manifest_includes_namespace = false
  namespace                   = var.fine_tuning_team_namespace
}
