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
  gke_robot_service_account           = "service-${data.google_project.cluster.number}@container-engine-robot.iam.gserviceaccount.com"
  gke_robot_service_account_iam_email = "serviceAccount:${local.gke_robot_service_account}"

  # Define values that other values depend on
  _tenants_initial = {
    for name in var.federated_learning_tenant_names : name => {
      tenant_name                                        = name
      tenant_nodepool_name                               = format("%s-%s-p", local.cluster_name, name)
      tenant_nodepool_sa_name                            = format("%s-%s-n", local.cluster_name, name)
      tenant_apps_kubernetes_service_account_name        = local.tenant_apps_kubernetes_service_account_name
      tenant_apps_workload_identity_service_account_name = "serviceAccount:${local.cluster_project_id}.svc.id.goog[${name}/${local.tenant_apps_kubernetes_service_account_name}]"
    }
  }

  # These values depend on tenants_initial values
  _tenants_intermediate = {
    for name, values in local._tenants_initial : name => {
      tenant_name                                        = values.tenant_name
      tenant_nodepool_name                               = values.tenant_nodepool_name
      tenant_nodepool_sa_name                            = values.tenant_nodepool_sa_name
      tenant_nodepool_sa_email                           = "${values.tenant_nodepool_sa_name}@${local.service_account_domain}"
      tenant_apps_kubernetes_service_account_name        = values.tenant_apps_kubernetes_service_account_name
      tenant_apps_workload_identity_service_account_name = values.tenant_apps_workload_identity_service_account_name
    }
  }

  # This is the final map to use
  tenants = {
    for name, values in local._tenants_intermediate : name => {
      tenant_name                                        = values.tenant_name
      tenant_nodepool_name                               = values.tenant_nodepool_name
      tenant_nodepool_sa_name                            = values.tenant_nodepool_sa_name
      tenant_nodepool_sa_email                           = values.tenant_nodepool_sa_email
      tenant_nodepool_sa_iam_email                       = "serviceAccount:${values.tenant_nodepool_sa_email}"
      tenant_apps_kubernetes_service_account_name        = values.tenant_apps_kubernetes_service_account_name
      tenant_apps_workload_identity_service_account_name = values.tenant_apps_workload_identity_service_account_name

      kubernetes_templates_configuration_values = {
        namespace_name                              = values.tenant_name
        tenant_apps_kubernetes_service_account_name = values.tenant_apps_kubernetes_service_account_name
      }
    }
  }

  common_kubernetes_templates_configuration_values = {
    external_services_allowed_namespaces = var.federated_learning_external_services_allowed_namespaces
  }

  service_account_domain = "${local.cluster_project_id}.iam.gserviceaccount.com"

  node_pool_service_account_names = [
    for tenant in local.tenants : tenant.tenant_nodepool_sa_name
  ]

  node_pool_service_account_emails = [
    for tenant in local.tenants : tenant.tenant_nodepool_sa_email
  ]

  node_pool_service_account_iam_emails = [
    for tenant in local.tenants : tenant.tenant_nodepool_sa_iam_email
  ]

  # Put all service account names in a list so we can create them with a single
  # google_service_account resource
  service_account_names = concat(
    local.node_pool_service_account_names,
  )

  tenant_apps_kubernetes_service_account_name = "fl-ksa"

  federated_learning_firewall_policy_name = "${local.cluster_name}-federated-learning-firewall-policy"

  federated_learning_repository_id = "${local.unique_identifier_prefix}-fl-repository"
}

variable "federated_learning_cloud_storage_buckets" {
  default     = {}
  description = "Map describing the Cloud Storage buckets to create. Keys are bucket names."
  type = map(object({
    force_destroy      = bool
    versioning_enabled = bool
  }))
}

variable "federated_learning_cloud_storage_buckets_iam_bindings" {
  default     = []
  description = "Map of objects to configure Cloud IAM bindings for Cloud Storage buckets described by the federated_learning_cloud_storage_buckets variable. Keys are bucket names. Use the same names that you use in the federated_learning_cloud_storage_buckets variable"
  type = list(object({
    bucket_name = string
    member      = string
    role        = string
  }))
}

variable "federated_learning_external_services_allowed_namespaces" {
  default     = []
  description = "List of tenant names for which creating services that expose workloads directly is allowed."
  type        = list(string)
}

variable "federated_learning_tenant_names" {
  default     = ["fl-1"]
  description = "List of named tenants to be created in the cluster. Each tenant gets a dedicated node pool and Kubernetes namespace, isolated from other tenants."
  type        = list(string)
}

variable "federated_learning_node_pool_machine_type" {
  default     = "n4-standard-8"
  description = "Machine type of the node pools. If you need to enable confidential GKE nodes, ensure that the machine type supports that. Ref: https://cloud.google.com/kubernetes-engine/docs/how-to/confidential-gke-nodes"
  type        = string
}
