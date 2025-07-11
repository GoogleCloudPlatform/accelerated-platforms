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

resource "google_cloudbuild_trigger" "acp_ci_cd_runner_image" {
  filename = "test/ci-cd/cloudbuild/ci-cd/runner-image.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/ci-cd/runner-image.yaml",
    "test/ci-cd/container_images/dockerfile.runner",
  ]
  location        = var.build_location
  name            = "acp-ci-cd-runner-image"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }
}

resource "google_cloudbuild_trigger" "acp_ci_cd_terraform" {
  filename = "test/ci-cd/cloudbuild/acp-ci-cd-terraform.yaml"
  ignored_files = [
    "test/ci-cd/terraform/README.md",
  ]
  included_files = [
    "test/ci-cd/cloudbuild/acp-ci-cd-terraform.yaml",
    "test/ci-cd/terraform/**",
  ]
  location        = var.build_location
  name            = "acp-ci-cd-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_aiml_playground_terraform" {
  filename = "test/ci-cd/cloudbuild/platforms-gke-aiml-playground-terraform.yaml"
  ignored_files = [
    "platforms/gke-aiml/playground/README.md",
  ]
  included_files = [
    "platforms/gke-aiml/playground/**",
    "test/ci-cd/cloudbuild/platforms-gke-aiml-playground-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-aiml-playground-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_full_scripts" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/full-scripts.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
  ]
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/full-scripts.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-full-scripts"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_full_scripts_push" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/full-scripts.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
  ]
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/full-scripts.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-full-scripts-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_initialize_terraform" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/initialize.yaml"
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/initialize.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-initialize-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_initialize_terraform_push" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/initialize.yaml"
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/initialize.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-initialize-terraform-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_terraform" {
  filename = "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
  ]
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_terraform_push" {
  filename = "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
  ]
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-terraform-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_workloads_terraform" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/workloads.yaml"
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/workloads.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-workloads-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_workloads_terraform_push" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/core/workloads.yaml"
  included_files = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/**",
    "test/ci-cd/cloudbuild/platforms/gke/base/core/workloads.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-core-workloads-terraform-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_scripts" {
  filename = "test/ci-cd/cloudbuild/uc-federated-learning-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/use-cases/federated-learning/README.md"
  ]
  included_files = [
    # Include the whole core platform because we want to ensure that
    # changes to the base platform don't break this use case
    "platforms/gke/base/core/**",
    "platforms/gke/base/use-cases/federated-learning/**",
    "test/ci-cd/cloudbuild/uc-federated-learning-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-federated-learning-scripts"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_scripts_push" {
  filename = "test/ci-cd/cloudbuild/uc-federated-learning-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/use-cases/federated-learning/README.md"
  ]
  included_files = [
    # Include the whole core platform because we want to ensure that
    # changes to the base platform don't break this use case
    "platforms/gke/base/core/**",
    "platforms/gke/base/use-cases/federated-learning/**",
    "test/ci-cd/cloudbuild/uc-federated-learning-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-federated-learning-scripts-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_cross_device_scripts" {
  filename = "test/ci-cd/cloudbuild/uc-federated-learning-cross-device-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/use-cases/federated-learning/README.md",
    "platforms/gke/base/use-cases/federated-learning/cross-device/README.md"
  ]
  included_files = [
    # Include the whole core platform because we want to ensure that
    # changes to the base platform don't break this use case
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/jobset/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/workloads/lws/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/federated-learning/terraform/initialize/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/service_account/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/key_management_service/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/firewall/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_image_repository/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_node_pool/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/deploy.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/setup-environment.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh",
    "test/ci-cd/cloudbuild/uc-federated-learning-cross-device-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-fl-cross-device-scripts"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_cross_device_scripts_push" {
  filename = "test/ci-cd/cloudbuild/uc-federated-learning-cross-device-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/use-cases/federated-learning/README.md",
    "platforms/gke/base/use-cases/federated-learning/cross-device/README.md"
  ]
  included_files = [
    # Include the whole core platform because we want to ensure that
    # changes to the base platform don't break this use case
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/jobset/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/workloads/lws/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/federated-learning/terraform/initialize/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/service_account/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/key_management_service/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/firewall/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_image_repository/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_node_pool/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/deploy.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/setup-environment.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh",
    "test/ci-cd/cloudbuild/uc-federated-learning-cross-device-terraform.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-fl-cross-device-scripts-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_scripts" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts.yaml"
  included_files = [
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/hub_downloader/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/jobset/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/workloads/lws/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/initialize/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh",
    "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-inference-ref-arch-scripts"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _IAP_DOMAIN       = "accelerated-platforms.joonix.net"
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_scripts_push" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts.yaml"
  included_files = [
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/hub_downloader/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/jobset/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/workloads/lws/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/initialize/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh",
    "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-inference-ref-arch-scripts-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _IAP_DOMAIN       = "accelerated-platforms.joonix.net"
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_comfyui_scripts" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts-comfyui.yaml"
  included_files = [
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/initialize/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-comfyui.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-comfyui.sh",
    "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts-comfyui.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-inference-ref-arch-comfyui-scripts"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }

  substitutions = {
    _IAP_DOMAIN       = "accelerated-platforms.joonix.net"
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_push" {
  filename = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts-comfyui.yaml"
  included_files = [
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/custom_metrics_adapter/**",
    "platforms/gke/base/core/workloads/inference_gateway/**",
    "platforms/gke/base/core/workloads/priority_class/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/initialize/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-comfyui.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-comfyui.sh",
    "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/scripts-comfyui.yaml",
  ]
  location        = var.build_location
  name            = "platforms-gke-base-uc-inference-ref-arch-comfyui-scripts-push"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    push {
      branch       = "^main$"
      invert_regex = false
    }
  }

  substitutions = {
    _IAP_DOMAIN       = "accelerated-platforms.joonix.net"
    _WAIT_FOR_TRIGGER = google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id
  }
}

resource "google_cloudbuild_trigger" "uc_mftp_data_prep_gemma_it_build" {
  filename = "test/ci-cd/cloudbuild/uc-mftp-data-prep-gemma-it-build.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/uc-mftp-data-prep-gemma-it-build.yaml",
    "use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/src/**",
  ]
  location        = var.build_location
  name            = "uc-mftp-data-prep-gemma-it-build"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}

resource "google_cloudbuild_trigger" "uc_mftp_data_proc_ray_build" {
  filename = "test/ci-cd/cloudbuild/uc-mftp-data-proc-ray-build.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/uc-mftp-data-proc-ray-build.yaml",
    "use-cases/model-fine-tuning-pipeline/data-processing/ray/src/**",
  ]
  location        = var.build_location
  name            = "uc-mftp-data-proc-ray-build"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}

resource "google_cloudbuild_trigger" "uc_mftp_ft_pytorch_build" {
  filename = "test/ci-cd/cloudbuild/uc-mftp-ft-pytorch-build.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/uc-mftp-ft-pytorch-build.yaml",
    "use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/src/**",
  ]
  location        = var.build_location
  name            = "uc-mftp-ft-pytorch-build"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}

resource "google_cloudbuild_trigger" "uc_mftp_model_eval_build" {
  filename = "test/ci-cd/cloudbuild/uc-mftp-model-eval-build.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/uc-mftp-model-eval-build.yaml",
    "use-cases/model-fine-tuning-pipeline/model-eval/src/**",
  ]
  location        = var.build_location
  name            = "uc-mftp-model-eval-build"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}

resource "google_cloudbuild_trigger" "uc_rag_data_proc_ray_build" {
  filename = "test/ci-cd/cloudbuild/uc-rag-data-proc-ray-build.yaml"
  included_files = [
    "test/ci-cd/cloudbuild/uc-rag-data-proc-ray-build.yaml",
    "use-cases/rag-pipeline/data-preprocessing/src/**",
  ]
  location        = var.build_location
  name            = "uc-rag-data-proc-ray-build"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}
