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

resource "google_project_iam_custom_role" "gcs_fuse_user" {
  description = "GCS FUSE user permissions"
  permissions = [
    "storage.buckets.get",
    "storage.folders.create",
    "storage.folders.delete",
    "storage.folders.get",
    "storage.folders.list",
    "storage.folders.rename",
    "storage.managedFolders.create",
    "storage.managedFolders.delete",
    "storage.managedFolders.list",
    "storage.managedFolders.get",
    "storage.multipartUploads.abort",
    "storage.multipartUploads.create",
    "storage.multipartUploads.list",
    "storage.multipartUploads.listParts",
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",
    "storage.objects.move",
    "storage.objects.restore",
    "storage.objects.update",
  ]
  project = data.google_project.cluster.project_id
  role_id = local.cluster_gcsfuse_user_role_name
  title   = "${local.unique_identifier_prefix} GCS FUSE User"
}

resource "google_project_iam_custom_role" "gcs_fuse_viewer" {
  description = "GCS FUSE viewer permissions"
  permissions = [
    "storage.buckets.get",
    "storage.folders.get",
    "storage.folders.list",
    "storage.managedFolders.get",
    "storage.managedFolders.list",
    "storage.objects.get",
    "storage.objects.list",
  ]
  project = data.google_project.cluster.project_id
  role_id = local.cluster_gcsfuse_viewer_role_name
  title   = "${local.unique_identifier_prefix} GCS FUSE Viewer"
}
