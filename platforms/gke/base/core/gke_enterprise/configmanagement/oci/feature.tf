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

resource "google_gke_hub_feature" "configmanagement" {
  provider = google-beta

  location = "global"
  name     = "configmanagement"
  project  = google_project_service.anthosconfigmanagement_googleapis_com.project

  fleet_default_member_config {
    configmanagement {
      management = "MANAGEMENT_AUTOMATIC"

      config_sync {
        enabled       = true
        prevent_drift = var.configmanagement_prevent_drift
        source_format = "unstructured"

        oci {
          policy_dir  = var.configmanagement_policy_dir
          secret_type = "k8sserviceaccount"
          sync_repo   = local.oci_sync_repo
        }
      }
    }
  }
}

resource "google_gke_hub_feature_membership" "cluster_configmanagement" {
  provider = google-beta

  feature    = google_gke_hub_feature.configmanagement.name
  location   = google_gke_hub_feature.configmanagement.location
  membership = data.google_container_cluster.cluster.name
  project    = google_project_service.anthosconfigmanagement_googleapis_com.project

  configmanagement {
    management = "MANAGEMENT_AUTOMATIC"

    config_sync {
      enabled       = true
      prevent_drift = var.configmanagement_prevent_drift
      source_format = "unstructured"

      oci {
        policy_dir  = var.configmanagement_policy_dir
        secret_type = "k8sserviceaccount"
        sync_repo   = local.oci_sync_repo
      }
    }
  }
}
