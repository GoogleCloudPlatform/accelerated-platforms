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
  incoming_pubsub_topic_name = "${local.unique_identifier_prefix_underscore}_incoming_retail_event"
}

resource "google_pubsub_topic" "incoming_pubsub_topic" {
  name    = local.incoming_pubsub_topic_name
  project = google_project_service.pubsub_googleapis_com.project
}

resource "google_pubsub_topic_iam_binding" "publisher_binding" {
  project = google_project_service.pubsub_googleapis_com.project
  topic   = google_pubsub_topic.incoming_pubsub_topic.name
  role    = "roles/pubsub.publisher"
  members = [
    local.publisher_sa,
  ]
}

resource "google_pubsub_topic" "incoming_pubsub_dlq" {
  name    = "incoming_images_dlq"
  project = google_project_service.pubsub_googleapis_com.project
}

resource "google_pubsub_subscription" "incoming_pubsub_subscription" {
  name    = "incoming_subscription_ap"
  topic   = google_pubsub_topic.incoming_pubsub_topic.name
  project = google_project_service.pubsub_googleapis_com.project
}

resource "google_pubsub_topic" "workflow1_pubsub_topic" {
  name    = "workflow1_pubsub_topic"
  project = google_project_service.pubsub_googleapis_com.project
}

resource "google_pubsub_subscription" "incoming_dlq_subscription" {
  name    = "${google_pubsub_subscription.incoming_pubsub_subscription.name}_dlq"
  topic   = google_pubsub_topic.incoming_pubsub_dlq.id
  project = google_project_service.pubsub_googleapis_com.project
  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_binding" "incoming_dlq_grant_publish" {
  topic = google_pubsub_topic.incoming_pubsub_dlq.id
  role  = "roles/pubsub.publisher"
  members = [
    local.pubsub_sa_name,
  ]
  project = google_project_service.pubsub_googleapis_com.project
}

resource "google_pubsub_subscription_iam_binding" "incoming_grant_subscribe" {
  subscription = google_pubsub_subscription.incoming_pubsub_subscription.name
  role         = "roles/pubsub.subscriber"
  members = [
    local.pubsub_sa_name,
  ]
  project = google_project_service.pubsub_googleapis_com.project
}
