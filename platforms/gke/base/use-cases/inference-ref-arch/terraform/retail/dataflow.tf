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
  template_gcs_path = "gs://${google_storage_bucket.dataflow_staging_bucket.name}/templates/aggregate.template"
  df_tmp_path       = "gs://${google_storage_bucket.dataflow_staging_bucket.name}/tmp"
}

resource "google_dataflow_job" "batching_dataflow" {
  name    = local.dataflow_job_name
  region  = local.cluster_region
  project = google_project_service.dataflow_googleapis_com.project

  template_gcs_path = local.template_gcs_path
  temp_gcs_location = local.df_tmp_path

  enable_streaming_engine = true
  on_delete               = "cancel"

  depends_on = [
    google_project_iam_binding.pubsub_subscriber_role,
    google_project_iam_binding.pubsub_publisher_role,
    google_project_iam_binding.pubsub_viewer_role,
  ]
}