# Copyright 2023 Google LLC
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

# locals {
#   topics = {
#     aggregator_topic               = {
#       name = "aggregator-${var.platform_name}",
#       service_account_name = module.service_accounts.service_accounts_map[var.aggregator_compute_service_account].email
#     }
#     modelupdater_topic             = {
#       name = "modelupdater-${var.platform_name}",
#       service_account_name = module.service_accounts.service_accounts_map[var.model_updater_compute_service_account].email
#     }
#     aggregator_notifications_topic = {
#       name = "aggregator-notifications-${var.platform_name}",
#       service_account_name = module.service_accounts.service_accounts_map[var.aggregator_compute_service_account].email
#     }
#   }
# }

resource "google_pubsub_topic" "federated_learning_pubsub_topics" {
  for_each = toset(local.federated_learning_pubsub_topics)
  name = join("-", [local.unique_identifier_prefix, each.key, "topic"])

  depends_on = [
    google_project_service.pubsub_googleapis_com
  ]
}

resource "google_pubsub_topic" "federated_learning_pubsub_dead_letter_topics" {
  for_each = toset(local.federated_learning_pubsub_topics)
  name = join("-", [local.unique_identifier_prefix, each.key, "topic-dead-letter"])

  depends_on = [
    google_project_service.pubsub_googleapis_com
  ]
}

resource "google_pubsub_subscription" "federated_learning_pubsub_subscriptions" {
  for_each = toset(local.federated_learning_pubsub_topics)
  name = join("-", [local.unique_identifier_prefix, each.key, "subscription"])
  topic = google_pubsub_topic.federated_learning_pubsub_topics[each.key].name

  # 7 days
  message_retention_duration = "604800s"
  retain_acked_messages      = true

  ack_deadline_seconds = 10

  expiration_policy {
    # Dont expire
    ttl = ""
  }

  # enable_exactly_once_delivery = var.enable_exactly_once_delivery
}

resource "google_pubsub_subscription" "federated_learning_pubsub_dead_letter_queue_subscriptions" {
  for_each = toset(local.federated_learning_pubsub_topics)
  name = join("-", [local.unique_identifier_prefix, each.key, "dlq-subscription"])
  topic = google_pubsub_topic.federated_learning_pubsub_dead_letter_topics[each.key].name

  # 7 days
  message_retention_duration = "604800s"
  retain_acked_messages      = true

  ack_deadline_seconds = 10

  expiration_policy {
    # Dont expire
    ttl = ""
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.federated_learning_pubsub_dead_letter_topics[each.key].id
    max_delivery_attempts = 10
  }

  # enable_exactly_once_delivery = var.enable_exactly_once_delivery
}
