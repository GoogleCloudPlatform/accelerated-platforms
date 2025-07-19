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

data "google_compute_zones" "available" {
  project = google_project_service.confidentialcomputing_googleapis_com.project
  region  = var.cluster_region
}

resource "google_compute_instance_template" "instance_template" {
  for_each = var.federated_learning_cross_device_example_confidential_space_workloads
  project  = google_project_service.confidentialcomputing_googleapis_com.project
  region   = var.cluster_region

  name_prefix = "${local.unique_identifier_prefix}-"

  disk {
    auto_delete  = true
    boot         = true
    device_name  = join("-", [local.unique_identifier_prefix, each.key])
    source_image = var.federated_learning_cross_device_example_confidential_space_instance_image_name
    disk_type    = "pd-balanced"
    mode         = "READ_WRITE"
  }

  machine_type     = each.value.machine_type
  min_cpu_platform = "AMD Milan"

  metadata = {
    # Allocate 2GB to dev/shm
    # Workloads running inside confidential space need at least 2GB
    tee-dev-shm-size-kb              = 2000000
    tee-image-reference              = data.google_artifact_registry_docker_image.workload_image[each.key].self_link
    tee-container-log-redirect       = true
    tee-impersonate-service-accounts = var.federated_learning_cross_device_example_allowed_operator_service_accounts
    tee-monitoring-memory-enable     = true
    environment                      = var.platform_name
  }

  network_interface {
    access_config {
      network_tier = "PREMIUM"
    }

    network            = local.network_name
    subnetwork         = local.subnetwork_name
    subnetwork_project = google_project_service.confidentialcomputing_googleapis_com.project
  }

  scheduling {
    # Confidential compute can be set to "MIGRATE" only when
    # confidential_instance_type = "SEV" and min_cpu_platform = "AMD Milan"
    on_host_maintenance = "MIGRATE"
  }

  confidential_instance_config {
    confidential_instance_type = "SEV"
  }

  service_account {
    email  = google_service_account.federated_learning_cross_device_example_confidential_space_service_account[each.key].email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  shielded_instance_config {
    enable_integrity_monitoring = true
    enable_secure_boot          = true
    enable_vtpm                 = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_region_instance_group_manager" "instance_group" {
  for_each           = var.federated_learning_cross_device_example_confidential_space_workloads
  name               = join("-", [local.unique_identifier_prefix, each.key, "instance-group"])
  description        = join(" ", [local.unique_identifier_prefix, each.key, "instance group"])
  project            = google_project_service.confidentialcomputing_googleapis_com.project
  base_instance_name = join("-", [local.unique_identifier_prefix, each.key])

  version {
    instance_template = google_compute_instance_template.instance_template[each.key].id
    name              = join("-", [local.unique_identifier_prefix, each.key])
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.default[each.key].id
    initial_delay_sec = each.value.cooldown_period
  }

  update_policy {
    max_surge_fixed = length(data.google_compute_zones.available.names)
    minimal_action  = "REPLACE"
    type            = "PROACTIVE"
  }

  region = var.cluster_region
}

resource "google_compute_health_check" "default" {
  for_each            = var.federated_learning_cross_device_example_confidential_space_workloads
  project             = google_project_service.confidentialcomputing_googleapis_com.project
  name                = join("-", [local.unique_identifier_prefix, each.key, "http-health-check"])
  timeout_sec         = 10
  check_interval_sec  = 30
  healthy_threshold   = 1
  unhealthy_threshold = 3
  http_health_check {
    request_path = "/healthz"
    port         = "8082"
  }
}

resource "google_compute_region_autoscaler" "autoscaler" {
  for_each = var.federated_learning_cross_device_example_confidential_space_workloads
  name     = join("-", [local.unique_identifier_prefix, each.key, "autoscaler"])
  project  = google_project_service.confidentialcomputing_googleapis_com.project
  region   = var.cluster_region
  target   = google_compute_region_instance_group_manager.instance_group[each.key].id

  autoscaling_policy {
    max_replicas = each.value.max_replicas
    min_replicas = each.value.min_replicas
    # The number of seconds that the autoscaler should wait before it starts collecting information from a new instance.
    cooldown_period = each.value.cooldown_period

    metric {
      name                       = "pubsub.googleapis.com/subscription/num_undelivered_messages"
      filter                     = "resource.type = pubsub_subscription AND resource.label.subscription_id = ${local.unique_identifier_prefix}-${each.key}-subscription"
      single_instance_assignment = each.value.autoscaling_jobs_per_instance
    }
  }

  # Required otherwise worker_instance_group hits resourceInUseByAnotherResource error when replacing
  lifecycle {
    replace_triggered_by = [google_compute_region_instance_group_manager.instance_group[each.key].id]
  }
}
