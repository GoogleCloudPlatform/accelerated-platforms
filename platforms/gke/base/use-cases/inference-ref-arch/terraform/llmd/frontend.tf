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
  final_artifact_repo_name = split("/", google_artifact_registry_repository.gradio_container_images.id)[5]
  image_destination        = "${local.cluster_region}-docker.pkg.dev/${data.google_project.cluster.project_id}/${local.final_artifact_repo_name}/${var.gradio_image_name}:${var.gradio_image_tag}"
}

data "google_service_account" "cloudbuild" {
  account_id = local.gradio_cloudbuild_service_account_name
  project    = local.gradio_cloudbuild_project_id
}

# Create Artifact Registry repository for gradio container images
resource "google_artifact_registry_repository" "gradio_container_images" {
  format        = "DOCKER"
  location      = local.cluster_region
  project       = data.google_project.cluster.project_id
  repository_id = "${local.unique_identifier_prefix}-${var.gradio_artifact_repo_name}"
}

# Permission CloudBuild service account to push images to Artifact Registry
resource "google_artifact_registry_repository_iam_member" "cloudbuild_artifactregistry_write" {
  location   = local.cluster_region
  member     = data.google_service_account.cloudbuild.member
  project    = data.google_project.cluster.project_id
  repository = google_artifact_registry_repository.gradio_container_images.repository_id
  role       = "roles/artifactregistry.writer"
}

# Build and submit gradio docker image to Artifact Registry
resource "terraform_data" "submit_docker_build" {
  provisioner "local-exec" {
    command     = <<-EOT
gcloud builds submit \
--config="platforms/gke/base/use-cases/inference-ref-arch/terraform/llmd/src/cloudbuild.yaml" \
--gcs-source-staging-dir="${data.google_storage_bucket.cloudbuild_source.url}/source" \
--project="${data.google_project.cluster.project_id}" \
--quiet \
--service-account="projects/${data.google_project.cluster.project_id}/serviceAccounts/${data.google_service_account.cloudbuild.email}" \
--substitutions=_DESTINATION="${local.image_destination}" \
platforms/gke/base/use-cases/inference-ref-arch/terraform/llmd/src
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    custom_sa_email        = data.google_service_account.cloudbuild.email
    hash_cloudbuild_config = filebase64sha256("${path.module}/src/cloudbuild.yaml")
    hash_entrypoint        = filebase64sha256("${path.module}/src/gradio_app.py")
    image_tag              = var.gradio_image_tag
    repository_id          = google_artifact_registry_repository.gradio_container_images.id
  }
}


# Apply gradio frontend manifests
resource "local_file" "gradio" {
  content = templatefile(
    "${path.module}/templates/frontend/gradio.tftpl.yaml",
    {
      namespace           = var.llmd_kubernetes_namespace
      internal_gateway_ip = google_compute_address.internal_gateway_ip.address
      image_destination   = local.image_destination
      service_name        = local.gradio_service_name
      deployment_name     = local.gradio_deployment_name
    }
  )
  file_permission = "0644"
  filename        = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/frontend/gradio.yaml"
}

module "kubectl_apply_gradio" {
  depends_on = [
    local_file.gradio,
    module.kubectl_apply_namespace,
    module.kubectl_apply_ext_gateway_res,
    terraform_data.submit_docker_build,
  ]

  source = "../../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.namespace_directory}/${var.llmd_kubernetes_namespace}/frontend/gradio.yaml"
  manifest_includes_namespace = true
}
