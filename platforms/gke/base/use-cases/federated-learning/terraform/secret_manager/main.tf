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
  parameters = {
    "AGGREGATED_GRADIENT_BUCKET_TEMPLATE"        = local.aggregated_gradient_bucket_name
    "AGGREGATION_BATCH_FAILURE_THRESHOLD"        = var.federated_learning_aggregation_batch_failure_threshold
    "AGGREGATOR_NOTIF_PUBSUB_SUBSCRIPTION"       = local.aggregator_notifications_pubsub_subscription
    "AGGREGATOR_NOTIF_PUBSUB_TOPIC"              = local.aggregator_notifications_pubsub_topic
    "AGGREGATOR_PUBSUB_SUBSCRIPTION"             = local.aggregator_pubsub_subscription
    "AGGREGATOR_PUBSUB_TOPIC"                    = local.aggregator_pubsub_topic
    "ALLOW_ROOTED_DEVICES"                       = var.federated_learning_allow_rooted_devices
    "CLIENT_GRADIENT_BUCKET_TEMPLATE"            = local.client_gradient_bucket_name
    "COLLECTOR_BATCH_SIZE"                       = var.federated_learning_collector_batch_size
    "DOWNLOAD_CHECKPOINT_TOKEN_DURATION"         = var.federated_learning_download_checkpoint_token_duration
    "DOWNLOAD_PLAN_TOKEN_DURATION"               = var.federated_learning_download_plan_token_duration
    "ENCRYPTION_KEY_SERVICE_A_BASE_URL"          = var.federated_learning_encryption_key_service_a_base_url
    "ENCRYPTION_KEY_SERVICE_B_BASE_URL"          = var.federated_learning_encryption_key_service_b_base_url
    "ENCRYPTION_KEY_SERVICE_A_CLOUDFUNCTION_URL" = var.federated_learning_encryption_key_service_a_cloudfunction_url
    "ENCRYPTION_KEY_SERVICE_B_CLOUDFUNCTION_URL" = var.federated_learning_encryption_key_service_b_cloudfunction_url
    "IS_AUTHENTICATION_ENABLED"                  = var.federated_learning_is_authentication_enabled
    "LOCAL_COMPUTE_TIMEOUT_MINUTES"              = var.federated_learning_local_compute_timeout_minutes
    "LOCK_DATABASE_NAME"                         = local.spanner_lock_database_name
    "METRICS_DATABASE_NAME"                      = local.spanner_database_name
    "METRICS_SPANNER_INSTANCE"                   = local.spanner_instance_name
    "MODEL_BUCKET_TEMPLATE"                      = local.model_bucket_name
    "MODEL_UPDATER_PUBSUB_SUBSCRIPTION"          = local.modelupdater_pubsub_subscription
    "MODEL_UPDATER_PUBSUB_TOPIC"                 = local.modelupdater_pubsub_topic
    "SERVICE_ACCOUNT_A"                          = var.federated_learning_service_account_a
    "SERVICE_ACCOUNT_B"                          = var.federated_learning_service_account_b
    "SPANNER_INSTANCE"                           = local.spanner_instance_name
    "TASK_DATABASE_NAME"                         = local.spanner_database_name
    "UPLOAD_GRADIENT_TOKEN_DURATION"             = var.federated_learning_upload_gradient_token_duration
    "UPLOAD_TIMEOUT_MINUTES"                     = var.federated_learning_upload_timeout_minutes
    "WIP_PROVIDER_A"                             = var.federated_learning_wip_provider_a
    "WIP_PROVIDER_B"                             = var.federated_learning_wip_provider_b
  }
}

resource "google_secret_manager_secret" "federated_learning_worker_parameter" {
  for_each  = local.parameters
  secret_id = format("fc-%s-%s", var.platform_name, each.key)
  replication {
    auto {}
  }

  depends_on = [
    google_project_service.secret_manager_googleapis_com
  ]
}

resource "google_secret_manager_secret_version" "federated_learning_worker_parameter_value" {
  for_each    = local.parameters
  secret      = google_secret_manager_secret.federated_learning_worker_parameter[each.key].id
  secret_data = each.value
}
