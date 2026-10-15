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
  kubeconfig_directory               = "${path.module}/../../../../../kubernetes/kubeconfig"
  kubeconfig_file                    = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  manifests_directory                = "${local.namespace_directory}/${local.llmd_namespace}"
  manifests_directory_root           = "${path.module}/../../../../kubernetes/manifests"
  namespace_directory                = "${local.manifests_directory_root}/namespace"
  workload_identity_principal_prefix = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}
