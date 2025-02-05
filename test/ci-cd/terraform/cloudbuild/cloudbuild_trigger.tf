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
}

resource "google_cloudbuild_trigger" "platforms_gke_aiml_playground_terraform_destroy" {
  location        = var.build_location
  name            = "platforms-gke-aiml-playground-terraform-destroy"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id
  substitutions = {
    "_ENVIRONMENT_NAME" = "dev"
  }

  git_file_source {
    path       = "test/ci-cd/cloudbuild/platforms-gke-aiml-playground-terraform-destroy.yaml"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
    repo_type  = "GITHUB"
    revision   = "refs/heads/main"
  }

  source_to_build {
    ref        = "refs/heads/main"
    repo_type  = "GITHUB"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
  }
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_terraform" {
  filename = "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform.yaml"
  ignored_files = [
    "platforms/gke/base/core/README.md",
  ]
  included_files = [
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
}

resource "google_cloudbuild_trigger" "platforms_gke_base_core_terraform_destroy" {
  location        = var.build_location
  name            = "platforms-gke-base-core-terraform-destroy"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id
  substitutions = {
    "_PLATFORM_NAME" = "dev"
  }

  git_file_source {
    path       = "test/ci-cd/cloudbuild/platforms-gke-base-core-terraform-destroy.yaml"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
    repo_type  = "GITHUB"
    revision   = "refs/heads/main"
  }

  source_to_build {
    ref        = "refs/heads/main"
    repo_type  = "GITHUB"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
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

resource "google_cloudbuild_trigger" "uc_federated_learning_terraform" {
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
  name            = "uc-federated-learning-terraform"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.accelerated_platforms.id

    pull_request {
      branch          = "^main$|^int-federated-learning$|^fl-"
      comment_control = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY"
      invert_regex    = false
    }
  }
}

resource "google_cloudbuild_trigger" "uc_federated_learning_terraform_destroy" {
  location        = var.build_location
  name            = "uc-federated-learning-terraform-destroy"
  project         = data.google_project.build.project_id
  service_account = google_service_account.integration.id
  substitutions = {
    "_PLATFORM_NAME" = "dev"
  }

  git_file_source {
    path       = "test/ci-cd/cloudbuild/uc-federated-learning-terraform-destroy.yaml"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
    repo_type  = "GITHUB"
    revision   = "refs/heads/main"
  }

  source_to_build {
    ref        = "refs/heads/main"
    repo_type  = "GITHUB"
    repository = google_cloudbuildv2_repository.accelerated_platforms.id
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