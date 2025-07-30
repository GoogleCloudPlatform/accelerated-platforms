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

###################################################################################################

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

###################################################################################################

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

###################################################################################################

locals {
  platforms_gke_base_core_ap_full_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/ap-full-scripts.yaml"
  platforms_gke_base_core_ap_full_scripts_ignore = [
    "platforms/gke/base/core/deploy-ap.sh",
    "platforms/gke/base/core/deploy-standard.sh",
    "platforms/gke/base/core/deploy-tutorial-ap.sh",
    "platforms/gke/base/core/deploy-tutorial-standard.sh",
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/core/teardown-ap.sh",
    "platforms/gke/base/core/teardown-standard.sh",
    "platforms/gke/base/core/teardown-tutorial-ap.sh",
    "platforms/gke/base/core/teardown-tutorial-standard.sh"
  ]
  platforms_gke_base_core_ap_full_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/scripts/platforms/gke/base/core/ap-full-deploy.sh",
    "test/ci-cd/scripts/platforms/gke/base/core/ap-full-teardown.sh",
    local.platforms_gke_base_core_ap_full_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_ap_full_scripts" {
  filename        = local.platforms_gke_base_core_ap_full_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_ap_full_scripts_ignore
  included_files  = local.platforms_gke_base_core_ap_full_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-ap-full-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_core_ap_full_scripts_push" {
  filename        = local.platforms_gke_base_core_ap_full_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_ap_full_scripts_ignore
  included_files  = local.platforms_gke_base_core_ap_full_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-ap-full-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_core_full_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/standard-full-scripts.yaml"
  platforms_gke_base_core_full_scripts_ignore = [
    "platforms/gke/base/core/deploy-ap.sh",
    "platforms/gke/base/core/deploy-standard.sh",
    "platforms/gke/base/core/deploy-tutorial-ap.sh",
    "platforms/gke/base/core/deploy-tutorial-standard.sh",
    "platforms/gke/base/core/README.md",
    "platforms/gke/base/core/teardown-ap.sh",
    "platforms/gke/base/core/teardown-standard.sh",
    "platforms/gke/base/core/teardown-tutorial-ap.sh",
    "platforms/gke/base/core/teardown-tutorial-standard.sh"
  ]
  platforms_gke_base_core_full_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/**",
    "test/ci-cd/scripts/platforms/gke/base/core/core-full-deploy.sh",
    "test/ci-cd/scripts/platforms/gke/base/core/core-full-teardown.sh",
    local.platforms_gke_base_core_full_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_full_scripts" {
  filename        = local.platforms_gke_base_core_full_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_full_scripts_ignore
  included_files  = local.platforms_gke_base_core_full_scripts_include
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
  filename        = local.platforms_gke_base_core_full_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_full_scripts_ignore
  included_files  = local.platforms_gke_base_core_full_scripts_include
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

###################################################################################################

locals {
  platforms_gke_base_core_initialize_terraform_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/initialize.yaml"
  platforms_gke_base_core_initialize_terraform_ignore = [
  ]
  platforms_gke_base_core_initialize_terraform_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    local.platforms_gke_base_core_initialize_terraform_cb_yaml,
  ]

}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_initialize_terraform" {
  filename        = local.platforms_gke_base_core_initialize_terraform_cb_yaml
  ignored_files   = local.platforms_gke_base_core_initialize_terraform_ignore
  included_files  = local.platforms_gke_base_core_initialize_terraform_include
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
  filename        = local.platforms_gke_base_core_initialize_terraform_cb_yaml
  ignored_files   = local.platforms_gke_base_core_initialize_terraform_ignore
  included_files  = local.platforms_gke_base_core_initialize_terraform_include
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

###################################################################################################

locals {
  platforms_gke_base_core_ap_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/ap-scripts.yaml"
  platforms_gke_base_core_ap_scripts_ignore = [
  ]
  platforms_gke_base_core_ap_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster_ap/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/gke_enterprise/fleet_membership/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/deploy-ap.sh",
    "platforms/gke/base/core/teardown-ap.sh",
    local.platforms_gke_base_core_ap_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_ap_scripts" {
  filename        = local.platforms_gke_base_core_ap_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_ap_scripts_ignore
  included_files  = local.platforms_gke_base_core_ap_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-ap-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_core_ap_scripts_push" {
  filename        = local.platforms_gke_base_core_ap_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_ap_scripts_ignore
  included_files  = local.platforms_gke_base_core_ap_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-ap-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_core_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/standard-scripts.yaml"
  platforms_gke_base_core_scripts_ignore = [
  ]
  platforms_gke_base_core_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/container_node_pool/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/gke_enterprise/fleet_membership/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/workloads/kueue/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    local.platforms_gke_base_core_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_scripts" {
  filename        = local.platforms_gke_base_core_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_scripts_ignore
  included_files  = local.platforms_gke_base_core_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_core_scripts_push" {
  filename        = local.platforms_gke_base_core_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_scripts_ignore
  included_files  = local.platforms_gke_base_core_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_core_tutorial_ap_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/tutorial-ap-scripts.yaml"
  platforms_gke_base_core_tutorial_ap_scripts_ignore = [
  ]
  platforms_gke_base_core_tutorial_ap_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster_ap/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/deploy-tutorial-ap.sh",
    "platforms/gke/base/core/teardown-tutorial-ap.sh",
    local.platforms_gke_base_core_tutorial_ap_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_tutorial_ap_scripts" {
  filename        = local.platforms_gke_base_core_tutorial_ap_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_tutorial_ap_scripts_ignore
  included_files  = local.platforms_gke_base_core_tutorial_ap_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-tutorial-ap-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_core_tutorial_ap_scripts_push" {
  filename        = local.platforms_gke_base_core_tutorial_ap_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_tutorial_ap_scripts_ignore
  included_files  = local.platforms_gke_base_core_tutorial_ap_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-tutorial-ap-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_core_tutorial_standard_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/tutorial-standard-scripts.yaml"
  platforms_gke_base_core_tutorial_standard_scripts_ignore = [
  ]
  platforms_gke_base_core_tutorial_standard_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/custom_compute_class/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/auto_monitoring/**",
    "platforms/gke/base/core/workloads/cluster_credentials/**",
    "platforms/gke/base/core/deploy-tutorial-standard.sh",
    "platforms/gke/base/core/teardown-tutorial-standard.sh",
    local.platforms_gke_base_core_tutorial_standard_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_tutorial_standard_scripts" {
  filename        = local.platforms_gke_base_core_tutorial_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_tutorial_standard_scripts_ignore
  included_files  = local.platforms_gke_base_core_tutorial_standard_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-tutorial-standard-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_core_tutorial_standard_scripts_push" {
  filename        = local.platforms_gke_base_core_tutorial_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_core_ap_scripts_ignore
  included_files  = local.platforms_gke_base_core_ap_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-core-tutorial-standard-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_core_workloads_terraform_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/core/workloads.yaml"
  platforms_gke_base_core_workloads_terraform_ignore = [
  ]
  platforms_gke_base_core_workloads_terraform_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/workloads/**",
    local.platforms_gke_base_core_workloads_terraform_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_workloads_terraform" {
  filename        = local.platforms_gke_base_core_workloads_terraform_cb_yaml
  ignored_files   = local.platforms_gke_base_core_workloads_terraform_ignore
  included_files  = local.platforms_gke_base_core_workloads_terraform_include
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
  filename        = local.platforms_gke_base_core_workloads_terraform_cb_yaml
  ignored_files   = local.platforms_gke_base_core_workloads_terraform_ignore
  included_files  = local.platforms_gke_base_core_workloads_terraform_include
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

###################################################################################################

locals {
  platforms_gke_base_uc_federated_learning_standard_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/federated-learning/standard-scripts.yaml"
  platforms_gke_base_uc_federated_learning_standard_scripts_ignore = [
  ]
  platforms_gke_base_uc_federated_learning_standard_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/cloudbuild/initialize/**",
    "platforms/gke/base/core/gke_enterprise/configmanagement/oci/**",
    "platforms/gke/base/core/gke_enterprise/fleet_membership/**",
    "platforms/gke/base/core/gke_enterprise/policycontroller/**",
    "platforms/gke/base/core/gke_enterprise/servicemesh/**",
    "platforms/gke/base/core/huggingface/initialize/**",
    "platforms/gke/base/core/initialize/**",
    "platforms/gke/base/core/networking/**",
    "platforms/gke/base/core/deploy.sh",
    "platforms/gke/base/core/teardown.sh",
    "platforms/gke/base/use-cases/federated-learning/common.sh",
    "platforms/gke/base/use-cases/federated-learning/deploy.sh",
    "platforms/gke/base/use-cases/federated-learning/teardown.sh",
    "platforms/gke/base/use-cases/federated-learning/terraform/_shared_config",
    "platforms/gke/base/use-cases/federated-learning/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/config_management/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_image_repository/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_node_pool/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/firewall/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/initialize/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/key_management_service/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/service_account/**",
    local.platforms_gke_base_uc_federated_learning_standard_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_standard_scripts" {
  filename        = local.platforms_gke_base_uc_federated_learning_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_federated_learning_standard_scripts_ignore
  included_files  = local.platforms_gke_base_uc_federated_learning_standard_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-uc-federated-learning-standard-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_standard_scripts_push" {
  filename        = local.platforms_gke_base_uc_federated_learning_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_federated_learning_standard_scripts_ignore
  included_files  = local.platforms_gke_base_uc_federated_learning_standard_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-uc-federated-learning-standard-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/federated-learning/standard-scripts-cross-device.yaml"
  platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_ignore = [
  ]
  platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_include = [
    "platforms/gke/base/_shared_config/**",
    "platforms/gke/base/core/container_cluster/**",
    "platforms/gke/base/core/cloudbuild/initialize/**",
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
    "platforms/gke/base/use-cases/federated-learning/common.sh",
    "platforms/gke/base/use-cases/federated-learning/deploy.sh",
    "platforms/gke/base/use-cases/federated-learning/teardown.sh",
    "platforms/gke/base/use-cases/federated-learning/terraform/_shared_config",
    "platforms/gke/base/use-cases/federated-learning/terraform/initialize/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/service_account/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/key_management_service/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/config_management/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/firewall/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_image_repository/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/private_google_access/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/container_node_pool/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/cloud_storage/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/build_workload_images/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/network/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/pubsub/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/spanner/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/secret_manager/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/confidential_space/**",
    "platforms/gke/base/use-cases/federated-learning/terraform/example_cross_device/**",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/deploy.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/setup-environment.sh",
    "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh",
    local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_cross_device_standard_scripts" {
  filename        = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_ignore
  included_files  = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-uc-fl-cross-device-standard-scripts"
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

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_push" {
  filename        = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_ignore
  included_files  = local.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_include
  location        = var.build_location
  name            = "platforms-gke-base-uc-fl-cross-device-standard-scripts-push"
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

###################################################################################################

locals {
  platforms_gke_base_uc_inference_ref_arch_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/standard-scripts.yaml"
  platforms_gke_base_uc_inference_ref_arch_scripts_ignore = [
  ]
  platforms_gke_base_uc_inference_ref_arch_scripts_include = [
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
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu/**",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh",
    "platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh",
    local.platforms_gke_base_uc_inference_ref_arch_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_scripts" {
  filename        = local.platforms_gke_base_uc_inference_ref_arch_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_inference_ref_arch_scripts_ignore
  included_files  = local.platforms_gke_base_uc_inference_ref_arch_scripts_include
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
  filename        = local.platforms_gke_base_uc_inference_ref_arch_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_inference_ref_arch_scripts_ignore
  included_files  = local.platforms_gke_base_uc_inference_ref_arch_scripts_include
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

###################################################################################################

locals {
  platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_cb_yaml = "test/ci-cd/cloudbuild/platforms/gke/base/use-cases/inference-ref-arch/standard-scripts-comfyui.yaml"
  platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_ignore = [
  ]
  platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_include = [
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
    local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_cb_yaml,
  ]
}

resource "google_cloudbuild_trigger" "platforms_gke_base_uc_inference_ref_arch_comfyui_scripts" {
  filename        = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_ignore
  included_files  = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_include
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
  filename        = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_cb_yaml
  ignored_files   = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_ignore
  included_files  = local.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_include
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

###################################################################################################

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
