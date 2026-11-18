# Copyright 2026 Google LLC
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

# Benchmark infrastructure:
# - a private Cloud Storage bucket that the inference-perf client Jobs upload
#   their reports to,
# - IAM for the Kubernetes service account that the client Jobs run as. Thanks
#   to namespace sameness and the fleet-wide workload identity pool, the same
#   principal identifies the client Jobs in every regional cluster.
#
# https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/docs/config.md

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  workload_identity_principal = "principal://iam.googleapis.com/projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${var.project_id}.svc.id.goog/subject/ns/${var.kubernetes_namespace}/sa/${var.kubernetes_service_account}"
}

resource "google_project_service" "services" {
  for_each = toset([
    "monitoring.googleapis.com",
    "storage.googleapis.com",
  ])

  disable_dependent_services = false
  disable_on_destroy         = false
  project                    = var.project_id
  service                    = each.value
}

resource "google_storage_bucket" "results" {
  depends_on = [google_project_service.services]

  force_destroy               = true
  location                    = var.bucket_location
  name                        = var.bucket_name
  project                     = var.project_id
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = var.results_retention_days
    }
  }
}

# Read and write report objects.
resource "google_storage_bucket_iam_member" "results_object_user" {
  # Re-create the binding when the bucket is replaced (for example, when its
  # location changes), otherwise the binding is silently lost.
  lifecycle {
    replace_triggered_by = [google_storage_bucket.results]
  }

  bucket = google_storage_bucket.results.name
  member = local.workload_identity_principal
  role   = "roles/storage.objectUser"
}

# inference-perf v0.7.0 calls `storage.Client().lookup_bucket()` before it
# uploads, which needs `storage.buckets.get`. roles/storage.objectUser doesn't
# include it; roles/storage.legacyBucketReader grants only
# `storage.buckets.get` and `storage.objects.list` on this bucket.
resource "google_storage_bucket_iam_member" "results_bucket_reader" {
  # Re-create the binding when the bucket is replaced (for example, when its
  # location changes), otherwise the binding is silently lost.
  lifecycle {
    replace_triggered_by = [google_storage_bucket.results]
  }

  bucket = google_storage_bucket.results.name
  member = local.workload_identity_principal
  role   = "roles/storage.legacyBucketReader"
}

# Optional server-side metrics: inference-perf queries Google Cloud Managed
# Service for Prometheus when `metrics.prometheus.google_managed` is true.
resource "google_project_iam_member" "monitoring_viewer" {
  depends_on = [google_project_service.services]

  member  = local.workload_identity_principal
  project = var.project_id
  role    = "roles/monitoring.viewer"
}

output "bucket_name" {
  value = google_storage_bucket.results.name
}

output "workload_identity_principal" {
  value = local.workload_identity_principal
}
