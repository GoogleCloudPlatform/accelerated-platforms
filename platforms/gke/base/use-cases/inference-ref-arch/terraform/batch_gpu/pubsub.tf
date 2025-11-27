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

resource "google_pubsub_topic" "prompt_messages_topic" {
  project = data.google_project.cluster.project_id

  name = local.ira_batch_pubsub_prompt_messages_topic_name
}

resource "google_pubsub_topic" "prompt_messages_topic_dead_letter" {
  project = data.google_project.cluster.project_id

  name = local.ira_batch_pubsub_prompt_messages_topic_dead_letter_name
}

resource "google_pubsub_subscription" "prompt_messages_subscription" {
  project = data.google_project.cluster.project_id

  name  = local.ira_batch_pubsub_prompt_messages_subscription_name
  topic = google_pubsub_topic.prompt_messages_topic.id

  # 20 minutes
  message_retention_duration = "1200s"
  retain_acked_messages      = true

  ack_deadline_seconds = 600

  expiration_policy {
    ttl = "300000.5s"
  }

  retry_policy {
    minimum_backoff = "10s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.prompt_messages_topic_dead_letter.id
    max_delivery_attempts = 10
  }
}

resource "google_pubsub_subscription" "prompt_messages_dead_letter_subscription" {
  project = data.google_project.cluster.project_id

  name  = local.ira_batch_pubsub_prompt_messages_subscription_dead_letter_name
  topic = google_pubsub_topic.prompt_messages_topic_dead_letter.id

  # 20 minutes
  message_retention_duration = "1200s"
  retain_acked_messages      = true

  ack_deadline_seconds = 600

  expiration_policy {
    ttl = "300000.5s"
  }

  retry_policy {
    minimum_backoff = "10s"
  }
}
