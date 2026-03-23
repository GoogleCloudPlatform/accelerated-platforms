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
  cluster_wi_principal_prefix      = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  rl_on_tpu_ksa_member             = "${local.cluster_wi_principal_prefix}/ns/${local.rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name}/sa/${local.rl_tpu_reinforcement_learning_on_tpu_kubernetes_service_account_name}"
  rl_mlflow_ksa_member             = "${local.cluster_wi_principal_prefix}/ns/${local.rl_cpu_reinforcement_learning_mlflow_kubernetes_namespace_name}/sa/${local.rl_cpu_reinforcement_learning_mlflow_kubernetes_service_account_name}"
  rl_dataset_downloader_ksa_member = "${local.cluster_wi_principal_prefix}/ns/${local.rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_namespace_name}/sa/${local.rl_cpu_reinforcement_learning_dataset_downloader_kubernetes_service_account_name}"
}

resource "google_storage_bucket_iam_member" "hub_models_rl_on_tpu_ksa" {
  bucket = data.google_storage_bucket.hub_models.name
  member = local.rl_on_tpu_ksa_member
  role   = local.cluster_gcsfuse_user_role
}

resource "google_project_iam_member" "gcsfuse_user_member_ira_offline_batch_cpu_dataset_downloader_ksa" {
  project = data.google_project.cluster.project_id
  member  = local.rl_dataset_downloader_ksa_member
  role    = local.cluster_gcsfuse_user_role
}
