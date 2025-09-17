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
  cloudbuild_trigger_url_prefix = "https://cloudbuild.googleapis.com/v1/projects/${data.google_project.build.project_id}/locations/${var.build_location}/triggers"
}

resource "google_cloud_scheduler_job" "acp_ci_cd_project_cleaner_hourly" {
  name      = "acp-ci-cd-project-cleaner-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 * * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.acp_ci_cd_project_cleaner.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "acp_ci_cd_runner_image_daily" {
  name      = "acp-ci-cd-runner-image-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 6 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.acp_ci_cd_runner_image.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_ap_full_scripts" {
  name      = "platforms-gke-base-core-ap-full-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_ap_full_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_full_scripts" {
  name      = "platforms-gke-base-core-full-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_full_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_initialize_terraform" {
  name      = "platforms-gke-base-core-initialize-terraform-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_initialize_terraform_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_ap_scripts" {
  name      = "platforms-gke-base-core-ap-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_ap_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_scripts" {
  name      = "platforms-gke-base-core-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_tutorials_hf_gpu_model_scripts_ap" {
  name      = "${local.platforms_gke_base_tutorials_hf_gpu_model_scripts_ap_name}-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_tutorials_hf_gpu_model_scripts_ap_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_tutorials_hf_gpu_model_scripts_standard" {
  name      = "${local.platforms_gke_base_tutorials_hf_gpu_model_scripts_standard_name}-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_tutorials_hf_gpu_model_scripts_standard_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_tutorials_hf_tpu_model_scripts_ap" {
  name      = "${local.platforms_gke_base_tutorials_hf_tpu_model_scripts_ap_name}-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_tutorials_hf_tpu_model_scripts_ap_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_tutorials_hf_tpu_model_scripts_standard" {
  name      = "${local.platforms_gke_base_tutorials_hf_tpu_model_scripts_standard_name}-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_tutorials_hf_tpu_model_scripts_standard_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_core_workloads_terraform" {
  name      = "platforms-gke-base-core-workloads-terraform-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_core_workloads_terraform_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_uc_federated_learning_standard_scripts" {
  name      = "platforms-gke-base-uc-federated_learning-standard-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_uc_federated_learning_standard_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_uc_federated_learning_cross_device_standard_scripts" {
  name      = "platforms-gke-base-uc-federated_learning-cross-device-standard-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_uc_federated_learning_cross_device_standard_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_uc_inference_ref_arch_scripts" {
  name      = "platforms-gke-base-uc-inference-ref-arch-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_uc_inference_ref_arch_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}

resource "google_cloud_scheduler_job" "platforms_gke_base_uc_inference_ref_arch_comfyui_scripts" {
  name      = "platforms-gke-base-uc-inference-ref-arch-comfyui-scripts-schedule"
  project   = data.google_project.build.project_id
  region    = var.build_location
  schedule  = "0 7 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    body        = base64encode(jsonencode({ "source" : { "branchName" = "main" } }))
    http_method = "POST"
    uri         = "${local.cloudbuild_trigger_url_prefix}/${google_cloudbuild_trigger.platforms_gke_base_uc_inference_ref_arch_comfyui_scripts_push.trigger_id}:run"

    oauth_token {
      service_account_email = google_service_account.cicd_sched.email
    }
  }
}
