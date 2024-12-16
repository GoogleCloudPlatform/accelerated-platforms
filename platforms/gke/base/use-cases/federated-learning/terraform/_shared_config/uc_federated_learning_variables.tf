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
  gke_robot_service_account           = "service-${data.google_project.default.number}@container-engine-robot.iam.gserviceaccount.com"
  gke_robot_service_account_iam_email = "serviceAccount:${local.gke_robot_service_account}"

  tenants = {
    for name in var.federated_learning_tenant_names : name => {
      tenant_name                                 = name
      tenant_nodepool_name                        = format("%s-%s-p", local.cluster_name, name)
      tenant_nodepool_sa_name                     = format("%s-%s-n", local.cluster_name, name)
      tenant_apps_sa_name                         = format("%s-%s-a", local.cluster_name, name)
      tenant_apps_kubernetes_service_account_name = local.tenant_apps_kubernetes_service_account_name
    }
  }

  node_pool_service_account_names = [
    for tenant in local.tenants : tenant.tenant_nodepool_sa_name
  ]

  node_pool_service_account_emails = [
    for tenant in local.tenants : "${tenant.tenant_nodepool_sa_name}@${var.cluster_project_id}.iam.gserviceaccount.com"
  ]

  node_pool_service_account_iam_emails = [
    for tenant in local.tenants : "serviceAccount:${tenant.tenant_nodepool_sa_name}@${var.cluster_project_id}.iam.gserviceaccount.com"
  ]

  apps_service_account_names = [
    for tenant in local.tenants : tenant.tenant_apps_sa_name
  ]

  apps_service_account_emails = [
    for tenant in local.tenants : "${tenant.tenant_apps_sa_name}@${var.cluster_project_id}.iam.gserviceaccount.com"
  ]

  apps_service_account_iam_emails = [
    for tenant in local.tenants : "serviceAccount:${tenant.tenant_apps_sa_name}@${var.cluster_project_id}.iam.gserviceaccount.com"
  ]

  # Put all service account names in a list so we can create them with a single
  # google_service_account resource
  service_account_names = concat(
    local.node_pool_service_account_names,
    local.apps_service_account_names,
  )

  tenant_apps_kubernetes_service_account_name = "fl-ksa"
}

variable "federated_learning_tenant_names" {
  default     = ["fl-1"]
  description = "List of named tenants to be created in the cluster. Each tenant gets a dedicated node pool and Kubernetes namespace, isolated from other tenants."
  type        = list(string)
}
