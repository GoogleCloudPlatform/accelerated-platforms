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

resource "google_workstations_workstation_config" "antigravity_crd_n2s2" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "antigravity-crd-n2s2"

  container {
    image = "${local.cloudbuild_cws_image_registry_url}/antigravity-crd:latest"
  }

  host {
    gce_instance {
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n2-standard-2"
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
}

resource "google_workstations_workstation_config" "antigravity_crd_n2s4" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "antigravity-crd-n2s4"

  container {
    image = "${local.cloudbuild_cws_image_registry_url}/antigravity-crd:latest"
  }

  host {
    gce_instance {
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n2-standard-4"
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
}

resource "google_workstations_workstation_config" "antigravity_crd_n2s8" {
  provider = google-beta

  idle_timeout           = "7200s"
  location               = local.workstation_cluster_region
  project                = local.workstation_cluster_project_id
  workstation_cluster_id = local.workstation_cluster_name
  workstation_config_id  = "antigravity-crd-n2s8"

  container {
    image = "${local.cloudbuild_cws_image_registry_url}/antigravity-crd:latest"
  }

  host {
    gce_instance {
      boot_disk_size_gb      = 100
      disable_ssh            = false
      machine_type           = "n2-standard-8"
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
}
