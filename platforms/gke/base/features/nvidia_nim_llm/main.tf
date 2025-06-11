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
  kubeconfig_directory     = "${path.module}/../../kubernetes/kubeconfig"
  manifests_directory_root = "${path.module}/../../kubernetes/manifests"
  namespace_directory      = "${local.manifests_directory_root}/namespace"

  kubernetes_namespace       = var.kubernetes_namespace != null ? var.kubernetes_namespace : "nim-${var.nvidia_nim_llm_release_name}"
  kubernetes_service_account = "${var.nvidia_nim_llm_release_name}-nim-llm"
}

provider "kubernetes" {
  config_path = "${local.kubeconfig_directory}/${var.kubeconfig_file_name}"
}

data "google_project" "cluster" {
  project_id = var.cluster_project_id
}

data "google_secret_manager_secret" "ncg_api_key" {
  project   = var.nvidia_ncg_api_key_secret_manager_project_id
  secret_id = var.nvidia_ncg_api_key_secret_manager_secret_name
}

data "google_secret_manager_secret_version" "ncg_api_key" {
  secret = data.google_secret_manager_secret.ncg_api_key.id
}

data "google_storage_bucket" "nvidia_nim_model_store" {
  name    = var.nvidia_model_store_bucket_name
  project = var.nvidia_model_store_bucket_project_id
}

data "helm_template" "nvidia_nim_llm" {
  chart               = "https://helm.ngc.nvidia.com/nim/charts/nim-llm-${var.nvidia_nim_llm_helm_chart_version}.tgz"
  kube_version        = var.kubernetes_version
  name                = var.nvidia_nim_llm_release_name
  repository_password = data.google_secret_manager_secret_version.ncg_api_key.secret_data
  repository_username = "$oauthtoken"
  skip_tests          = var.nvidia_nim_llm_helm_skip_tests
  validate            = var.validate_manifests
  values              = var.nvidia_nim_llm_helm_chart_values
}

data "local_file" "kubeconfig" {
  filename = "${local.kubeconfig_directory}/${var.kubeconfig_file_name}"
}

# Generate namespaces manifest if enabled
resource "local_file" "namespace_manifest" {
  for_each = toset(var.kubernetes_namespace_create ? ["new"] : [])

  filename = "${local.namespace_directory}/namespace-${local.kubernetes_namespace}.yaml"
  content = templatefile(
    "${path.module}/templates/kubernetes/namespace.tftpl.yaml",
    {
      namespace = local.kubernetes_namespace
    }
  )
}

# Apply namespaces manifest if enabled
module "kubectl_apply_namespace" {
  for_each = toset(var.kubernetes_namespace_create ? ["new"] : [])

  source = "../../modules/kubectl_apply"

  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.namespace_manifest["new"].filename
  manifest_includes_namespace = true
}

# TODO: Could this be replaced by a Secret Manager secret?
resource "kubernetes_secret" "ngc_api_key" {
  depends_on = [
    module.kubectl_apply_namespace
  ]

  data = {
    "NGC_API_KEY" = data.google_secret_manager_secret_version.ncg_api_key.secret_data
  }
  type = "Opaque"

  metadata {
    name      = "${var.nvidia_nim_llm_release_name}-ngc-api-key"
    namespace = local.kubernetes_namespace
  }
}

# TODO: Could this be replaced by a Secret Manager secret?
resource "kubernetes_secret" "ngc_image_pull" {
  depends_on = [
    module.kubectl_apply_namespace
  ]

  data = {
    ".dockerconfigjson" = jsonencode({
      "auths" = {
        "nvcr.io" = {
          "username" = "$oauthtoken"
          "password" = data.google_secret_manager_secret_version.ncg_api_key.secret_data
          "auth"     = base64encode("$oauthtoken:${data.google_secret_manager_secret_version.ncg_api_key.secret_data}")
        }
      }
    })
  }
  type = "kubernetes.io/dockerconfigjson"

  metadata {
    name      = "${var.nvidia_nim_llm_release_name}-ngc-image-pull"
    namespace = local.kubernetes_namespace
  }
}

resource "kubernetes_persistent_volume" "model_store" {
  metadata {
    name = "${local.kubernetes_namespace}-${var.nvidia_nim_llm_release_name}-nvidia-model-store"
  }

  spec {
    access_modes = [
      "ReadWriteMany",
    ]
    capacity = {
      storage : "500Gi"
    }
    persistent_volume_source {
      csi {
        driver            = "gcsfuse.csi.storage.gke.io"
        read_only         = true
        volume_attributes = { mountOptions = "file-cache:cache-file-for-range-read:true,file-cache:enable-parallel-downloads:true,file-cache:max-size-mb:-1,file-system:kernel-list-cache-ttl-secs:-1,gcs-connection:client-protocol:grpc,implicit-dirs,metadata-cache:stat-cache-max-size-mb:-1,metadata-cache:ttl-secs:-1,metadata-cache:type-cache-max-size-mb:-1" }
        volume_handle     = data.google_storage_bucket.nvidia_nim_model_store.name

      }
    }
    persistent_volume_reclaim_policy = "Retain"
    storage_class_name               = "gcsfuse-sc"
    volume_mode                      = "Filesystem"
  }
}

resource "kubernetes_persistent_volume_claim" "model_store" {
  depends_on = [
    module.kubectl_apply_namespace
  ]

  metadata {
    name      = "${var.nvidia_nim_llm_release_name}-nvidia-model-store"
    namespace = local.kubernetes_namespace
  }

  spec {
    access_modes = [
      "ReadWriteMany"
    ]
    resources {
      requests = {
        storage = "500Gi"
      }
    }
    volume_name        = kubernetes_persistent_volume.model_store.metadata[0].name
    storage_class_name = "gcsfuse-sc"
  }
}

resource "google_storage_bucket_iam_member" "service_account" {
  for_each = toset(var.nvidia_model_store_bucket_iam_roles)

  bucket = data.google_storage_bucket.nvidia_nim_model_store.name
  member = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject/ns/${local.kubernetes_namespace}/sa/${local.kubernetes_service_account}"
  role   = each.value
}

# Generated NVIDIA NIM LLM manifests
resource "local_file" "nim_llm_manifests" {
  filename = "${local.namespace_directory}/${local.kubernetes_namespace}/${var.nvidia_nim_llm_release_name}-manifests.yaml"
  content  = data.helm_template.nvidia_nim_llm.manifest
}

# Apply NVIDIA NIM LLM manifests
module "kubectl_apply_nim_llm_manifests" {
  depends_on = [
    kubernetes_persistent_volume_claim.model_store
  ]

  source = "../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.nim_llm_manifests.filename
  manifest_includes_namespace = false
  namespace                   = local.kubernetes_namespace
}
