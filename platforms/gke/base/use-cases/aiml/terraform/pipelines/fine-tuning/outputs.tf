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
  gsa_build_email       = google_service_account.fine_tuning_build.email
  model_ops_namespace   = var.fine_tuning_team_namespace
  model_serve_namespace = var.fine_tuning_team_namespace
}

output "environment_configuration" {
  value = <<EOT
MLP_AR_REPO_URL="${local.fine_tuning_ar_repository_url}"
MLP_BATCH_INFERENCE_IMAGE="${local.fine_tuning_ar_repository_url}/batch-inference:1.0.0"
MLP_BATCH_INFERENCE_KSA="${local.fine_tuning_kubernetes_service_accounts["batch-inference"].service_account_name}"
MLP_BENCHMARK_IMAGE="${local.fine_tuning_ar_repository_url}/benchmark:1.0.0"
MLP_BUILD_GSA="${local.gsa_build_email}"
MLP_CLOUDBUILD_BUCKET="${local.fine_tuning_bucket_cloudbuild_name}"
MLP_CLUSTER_LOCATION="${var.cluster_region}"
MLP_CLUSTER_NAME="${local.cluster_name}"
MLP_DATA_BUCKET="${local.fine_tuning_bucket_data_name}"
MLP_DATA_PREPARATION_IMAGE="${local.fine_tuning_ar_repository_url}/data-preparation:1.0.0"
MLP_DATA_PREPARATION_KSA="${local.fine_tuning_kubernetes_service_accounts["data-preparation"].service_account_name}"
MLP_DATA_PROCESSING_IMAGE="${local.fine_tuning_ar_repository_url}/data-processing:1.0.0"
MLP_DATA_PROCESSING_KSA="${local.fine_tuning_kubernetes_service_accounts["data-processing"].service_account_name}"
MLP_ENVIRONMENT_NAME="${var.platform_name}"
MLP_FINE_TUNING_IMAGE="${local.fine_tuning_ar_repository_url}/fine-tuning:1.0.0"
MLP_FINE_TUNING_KSA="${local.fine_tuning_kubernetes_service_accounts["fine-tuning"].service_account_name}"
MLP_GRADIO_MODEL_OPS_ENDPOINT="https://${local.endpoints["gradio"].host}"
MLP_KUBERNETES_NAMESPACE="${var.fine_tuning_team_namespace}"
MLP_LOCUST_NAMESPACE_ENDPOINT="https://${local.endpoints["locust"].host}"
MLP_MLFLOW_TRACKING_NAMESPACE_ENDPOINT="https://${local.endpoints["mlflow-tracking"].host}"
MLP_MODEL_BUCKET="${local.fine_tuning_bucket_model_name}"
MLP_MODEL_EVALUATION_IMAGE="${local.fine_tuning_ar_repository_url}/model-evaluation:1.0.0"
MLP_MODEL_EVALUATION_KSA="${local.fine_tuning_kubernetes_service_accounts["model-evaluation"].service_account_name}"
MLP_MODEL_OPS_KSA="${local.fine_tuning_kubernetes_service_accounts["model-ops"].service_account_name}"
MLP_MODEL_OPS_NAMESPACE="${local.model_ops_namespace}"
MLP_MODEL_SERVE_KSA="${local.fine_tuning_kubernetes_service_accounts["model-serve"].service_account_name}"
MLP_MODEL_SERVE_NAMESPACE="${local.model_serve_namespace}"
MLP_PROJECT_ID="${data.google_project.cluster.project_id}"
MLP_PROJECT_NUMBER="${data.google_project.cluster.number}"
MLP_RAY_DASHBOARD_NAMESPACE_ENDPOINT="https://${local.endpoints["ray-dashboard"].host}"
MLP_REGION="${var.cluster_region}"
MLP_UNIQUE_IDENTIFIER_PREFIX="${local.unique_identifier_prefix}"
EOT
}
