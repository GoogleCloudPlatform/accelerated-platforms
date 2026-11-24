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
  member = "${local.wi_member_principal_prefix}/${local.mft_kubernetes_service_accounts["mlflow"].service_account_name}"
  role   = "roles/storage.objectAdmin"
}

locals {
  # The hosts that the MLflow tracking server answers requests for: port forwarding to the
  # service, the service from inside the cluster and the endpoint of the gateway
  mlflow_allowed_hosts = [
    "localhost:*",
    "127.0.0.1:*",
    "${local.mlflow_endpoint.service_name}:${local.mlflow_endpoint.port}",
    "${local.mlflow_endpoint.service_name}.${local.mft_kubernetes_namespace}:${local.mlflow_endpoint.port}",
    "${local.mlflow_endpoint.service_name}.${local.mft_kubernetes_namespace}.svc:${local.mlflow_endpoint.port}",
    "${local.mlflow_endpoint.service_name}.${local.mft_kubernetes_namespace}.svc.cluster.local:${local.mlflow_endpoint.port}",
    local.mlflow_endpoint.host,
  ]
  mlflow_endpoint = local.mft_endpoints["mlflow-tracking"]
  mlflow_version  = "3.18.0"
}

resource "local_file" "mlflow_manifest" {
  content = templatefile(
    "${path.module}/templates/mlflow/manifests.tftpl.yaml",
    {
      allowed_hosts        = join(",", local.mlflow_allowed_hosts),
      bucket_name          = google_storage_bucket.data.name,
      cors_allowed_origins = "https://${local.mlflow_endpoint.host}",
      mlflow_version       = local.mlflow_version,
      service_account_name = local.mft_kubernetes_service_accounts["mlflow"].service_account_name,
      service_name         = local.mlflow_endpoint.service_name,
      service_port         = local.mlflow_endpoint.port,
    }
  )
  filename = "${local.mft_kubernetes_namespace_manifests_directory}/mlflow.yaml"
}

module "kubectl_apply_mlflow_manifest" {
  depends_on = [
    module.kubectl_apply_namespace_manifest,
  ]

  source = "../../../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.mlflow_manifest.filename
  manifest_includes_namespace = false
  namespace                   = local.mft_kubernetes_namespace
}
