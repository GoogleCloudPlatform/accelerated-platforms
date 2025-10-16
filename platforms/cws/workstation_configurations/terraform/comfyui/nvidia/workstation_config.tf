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

data "google_service_account" "default" {
  account_id = local.workstation_cluster_service_account_id
  project    = local.workstation_cluster_service_account_project_id
}

###########################################################################################
# A100
###########################################################################################
resource "google_workstations_workstation_config" "comfyui_nvidia_a100_40gb_x1" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-a100-40gb-x1"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "a2-highgpu-1g"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}



###########################################################################################
# P4
###########################################################################################
resource "google_workstations_workstation_config" "comfyui_nvidia_p4_x1_n1s4" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-p4-x1-n1s4"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-p4"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-4"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}

resource "google_workstations_workstation_config" "comfyui_nvidia_p4_x1_n1s8" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-p4-x1-n1s8"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-p4"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-8"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}



###########################################################################################
# T4
###########################################################################################
resource "google_workstations_workstation_config" "comfyui_nvidia_t4_x1_n1s4" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-t4-x1-n1s4"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-t4"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-4"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}

resource "google_workstations_workstation_config" "comfyui_nvidia_t4_x1_n1s8" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-t4-x1-n1s8"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-t4"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-8"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}



###########################################################################################
# V100
###########################################################################################
resource "google_workstations_workstation_config" "comfyui_nvidia_v100_x1_n1s4" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-v100-x1-n1s4"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-v100"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-4"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}

resource "google_workstations_workstation_config" "comfyui_nvidia_v100_x1_n1s8" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "comfyui-nvidia-v100-x1-n1s8"

  container {
    env = {
      COMFYUI_MODELS_BUCKET = "${local.cws_comfyui_model_bucket_name}"
    }
    image = "${local.cloudbuild_cws_image_registry_url}/comfyui:nvidia-latest"
  }

  host {
    gce_instance {
      accelerators {
        type  = "nvidia-tesla-v100"
        count = "1"
      }
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n1-standard-8"
      service_account        = data.google_service_account.default.email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 200
      fs_type        = "ext4"
      disk_type      = "pd-standard"
      reclaim_policy = "RETAIN"
    }
  }

  readiness_checks {
    path = "/"
    port = 80
  }
}
