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

data "google_artifact_registry_repository" "federated_learning_repository" {
  project       = local.cloudbuild_project_id
  repository_id = local.federated_learning_repository_id
  location      = local.cloudbuild_location
}

data "google_artifact_registry_docker_image" "workload_image" {
  for_each      = var.federated_learning_cross_device_example_confidential_space_workloads
  location      = data.google_artifact_registry_repository.federated_learning_repository.location
  repository_id = data.google_artifact_registry_repository.federated_learning_repository.repository_id
  image_name    = join("_", [replace(each.key, "-", "_"), "image"])
  project       = google_project_service.confidentialcomputing_googleapis_com.project
}
