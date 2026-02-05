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
  final_artifact_repo_name = split("/", google_artifact_registry_repository.comfyui_container_images.id)[5]
  image_destination        = "${local.cluster_region}-docker.pkg.dev/${data.google_project.cluster.project_id}/${local.final_artifact_repo_name}/${var.comfyui_image_name}:${var.comfyui_image_tag}-${local.comfyui_accelerator}"
}

resource "terraform_data" "submit_docker_build" {
  provisioner "local-exec" {
    command     = <<-EOT
gcloud builds submit \
--config="platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/src/cloudbuild.yaml" \
--gcs-source-staging-dir="${data.google_storage_bucket.cloudbuild_source.url}/source" \
--project="${data.google_project.cluster.project_id}" \
--quiet \
--service-account="projects/${data.google_project.cluster.project_id}/serviceAccounts/${data.google_service_account.cloudbuild.email}" \
--substitutions=_DOCKERFILE="${local.comfyui_dockerfile}",_DESTINATION="${local.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = local.acp_root
  }

  triggers_replace = {
    custom_nodes                 = sha256(join("", [for file in fileset("${local.acp_root}/modules/python/src/custom_nodes", "**") : filesha256("${local.acp_root}/modules/python/src/custom_nodes/${file}")]))
    custom_sa_email              = data.google_service_account.cloudbuild.email
    hash_cloudbuild_config       = filebase64sha256("${path.module}/src/cloudbuild.yaml")
    hash_dockerfile_no_manager   = filebase64sha256("${path.module}/src/Dockerfile.nvidia-no-manager")
    hash_dockerfile_with_manager = filebase64sha256("${path.module}/src/Dockerfile.nvidia-with-manager")
    hash_entrypoint              = filebase64sha256("${path.module}/src/entrypoint.sh")
    image_tag                    = var.comfyui_image_tag
    repository_id                = google_artifact_registry_repository.comfyui_container_images.id
  }
}
