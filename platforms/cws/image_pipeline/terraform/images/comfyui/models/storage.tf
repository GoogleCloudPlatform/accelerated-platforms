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

resource "google_storage_bucket" "models" {
  for_each = toset(var.cws_comfyui_model_bucket_name == null ? ["managed"] : [])

  force_destroy               = true
  location                    = local.cws_comfyui_model_bucket_location
  name                        = local.cws_comfyui_model_bucket_name
  project                     = data.google_project.model_bucket.project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }
}

data "google_storage_bucket" "models" {
  depends_on = [
    google_storage_bucket.models,
  ]

  name    = local.cws_comfyui_model_bucket_name
  project = data.google_project.model_bucket.project_id
}

resource "google_storage_bucket_object" "models_folder" {
  for_each = toset(
    [
      "checkpoints",
      "classifiers",
      "clip_vision",
      "controlnet",
      "diffusers",
      "diffusion_models",
      "embeddings",
      "gligen",
      "hypernetworks",
      "loras",
      "photomaker",
      "style_models",
      "text_encoders",
      "upscale_models",
      "vae",
      "vae_approx",
    ]
  )

  bucket  = data.google_storage_bucket.models.name
  content = " "
  name    = "${each.key}/"
}

resource "google_storage_bucket_iam_member" "models_storage_object_user" {
  depends_on = [
    data.google_storage_bucket.models,
  ]

  for_each = toset([
    data.google_service_account.vm_cws.member,
  ])

  bucket = data.google_storage_bucket.models.name
  member = each.key
  role   = "roles/storage.objectUser"
}

resource "google_storage_bucket_iam_member" "models_storage_bucket_viewer" {
  depends_on = [
    data.google_storage_bucket.models,
  ]

  for_each = toset([
    data.google_service_account.vm_cws.member,
  ])

  bucket = data.google_storage_bucket.models.name
  member = each.key
  role   = "roles/storage.bucketViewer"
}
