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

output "http_clone_url" {
  value = "${google_artifact_registry_repository.repository.location}-docker.pkg.dev/${google_artifact_registry_repository.repository.project}/${google_artifact_registry_repository.repository.name}"
}

output "location" {
  value = google_artifact_registry_repository.repository.location
}

output "name" {
  value = google_artifact_registry_repository.repository.name
}

output "project" {
  value = google_artifact_registry_repository.repository.project
}

output "repo" {
  value = google_artifact_registry_repository.repository
}
