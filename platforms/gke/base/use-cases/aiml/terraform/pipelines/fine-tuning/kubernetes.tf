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
  fine_tuning_manifests_directory           = "${path.module}/manifests/${local.unique_identifier_prefix}"
  fine_tuning_namespace_manifests_directory = "${local.fine_tuning_manifests_directory}/namespace/${var.fine_tuning_namespace}"

  fine_tuning_kubernetes_service_accounts = {
    batch-inference = {
      automount_service_account_token = false
      service_account_name            = "batch-inference"
    }
    data-preparation = {
      automount_service_account_token = false
      service_account_name            = "data-preparation"
    }
    data-processing = {
      automount_service_account_token = false
      service_account_name            = "data-processing"
    }
    fine-tuning = {
      automount_service_account_token = false
      service_account_name            = "fine-tuning"
    }
    model-evaluation = {
      automount_service_account_token = false
      service_account_name            = "model-evaluation"
    }
    model-ops = {
      automount_service_account_token = false
      service_account_name            = "model-ops"
    }
    model-serve = {
      automount_service_account_token = false
      service_account_name            = "model-serve"
    }
    ray-head = {
      # automount_service_account_token is required for autoscaler to work
      automount_service_account_token = true
      service_account_name            = "ray-head"
    }
    ray-worker = {
      automount_service_account_token = false
      service_account_name            = "ray-worker"
    }
  }

  kubeconfig_directory = "${path.module}/../../../../../_shared_config/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

provider "kubernetes" {
  #cluster_ca_certificate = base64decode(data.google_container_cluster.cluster.master_auth[0].cluster_ca_certificate)
  host     = "https://${data.google_container_cluster.cluster.control_plane_endpoints_config[0].dns_endpoint_config[0].endpoint}"
  insecure = true
  token    = data.google_client_config.default.access_token
}

resource "local_file" "kubernetes_namespace" {
  content = templatefile(
    "${path.module}/templates/kubernetes/namespace.tftpl.yaml",
    {
      namespace_name = var.fine_tuning_namespace,
    }
  )
  filename = "${local.fine_tuning_manifests_directory}/namespace/namespace-${var.fine_tuning_namespace}.yaml"
}

resource "local_file" "kubernetes_service_account" {
  for_each = local.fine_tuning_kubernetes_service_accounts

  content = templatefile(
    "${path.module}/templates/kubernetes/service-account.tftpl.yaml",
    {
      automount_service_account_token = each.value.automount_service_account_token,
      service_account_name            = each.value.service_account_name,
    }
  )
  filename = "${local.fine_tuning_manifests_directory}/namespace/${var.fine_tuning_namespace}/service-account-${each.key}.yaml"
}

resource "null_resource" "namespace_manifest" {
  provisioner "local-exec" {
    command = "kubectl apply --filename=${self.triggers.manifests}"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command = "kubectl delete --filename=${self.triggers.manifests}; exit 0"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers = {
    kubeconfig_file = data.local_file.kubeconfig.filename
    manifests       = local_file.kubernetes_namespace.filename
  }
}

resource "null_resource" "service_account_manifest" {
  depends_on = [
    null_resource.namespace_manifest
  ]

  for_each = local.fine_tuning_kubernetes_service_accounts

  provisioner "local-exec" {
    command = "kubectl --namespace=${self.triggers.namespace} apply --filename=${self.triggers.manifests}"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command = "kubectl --namespace=${self.triggers.namespace} delete -f ${self.triggers.manifests}; exit 0"
    environment = {
      KUBECONFIG = self.triggers.kubeconfig_file
    }
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers = {
    kubeconfig_file = data.local_file.kubeconfig.filename
    manifests       = local_file.kubernetes_service_account[each.key].filename
    namespace       = var.fine_tuning_namespace
  }
}
