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

output "use_case" {
  value = "training-ref-arch"
}

output "mft_data_bucket_name" {
  value = local.mft_data_bucket_name
}

output "mft_data_preparation_image_url" {
  value = local.mft_data_preparation_image_url
}

output "mft_data_preparation_service_account_name" {
  value = local.mft_data_preparation_service_account_name
}

output "mft_data_processing_image_url" {
  value = local.mft_data_processing_image_url
}

output "mft_data_processing_service_account_name" {
  value = local.mft_data_processing_service_account_name
}

output "mft_endpoint_mlflow_tracking_url" {
  value = "https://${local.mft_endpoints["mlflow-tracking"].host}"
}

output "mft_endpoint_ray_dashboard_url" {
  value = "https://${local.mft_endpoints["ray-dashboard"].host}"
}

output "mft_fine_tuning_image_url" {
  value = local.mft_fine_tuning_image_url
}

output "mft_fine_tuning_service_account_name" {
  value = local.mft_fine_tuning_service_account_name
}

output "mft_kubernetes_namespace" {
  value = local.mft_kubernetes_namespace
}

output "mft_bucket_model_name" {
  value = local.mft_bucket_model_name
}

output "mft_model_evaluation_image_url" {
  value = local.mft_model_evaluation_image_url
}

output "mft_model_evaluation_service_account_name" {
  value = local.mft_model_evaluation_service_account_name
}

output "mft_project_id" {
  value = local.mft_project_id
}

output "mft_region" {
  value = local.mft_region
}
