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
  source_path     = "${path.module}/src/comfyui-workflows/input-images/virtual-try-on"
  files_to_upload = fileset(local.source_path, "**/*.png")
}

resource "google_storage_bucket" "comfyui_input" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_input_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "comfyui_model" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_model_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "comfyui_output" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_output_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

resource "google_storage_bucket" "comfyui_workflow" {
  force_destroy               = true
  location                    = local.comfyui_cloud_storage_location
  name                        = local.comfyui_cloud_storage_workflow_bucket_name
  project                     = local.comfyui_cloud_storage_project_id
  uniform_bucket_level_access = true

  hierarchical_namespace {
    enabled = true
  }

  versioning {
    enabled = false
  }
}

data "google_storage_bucket" "cloudbuild_source" {
  name    = local.comfyui_cloudbuild_source_bucket_name
  project = local.comfyui_cloudbuild_project_id
}

resource "google_storage_bucket_object" "veo3-gcsimage" {
  bucket = google_storage_bucket.comfyui_input.name
  name   = "jellyfish.png"
  source = "src/comfyui-workflows/input-images/jellyfish.png"
}

resource "google_storage_bucket_object" "vto-gcsimage" {
  for_each = local.files_to_upload
  bucket   = google_storage_bucket.comfyui_input.name
  name     = "virtual-try-on/${each.key}"
  source   = "${local.source_path}/${each.key}"
}

resource "google_storage_bucket_object" "workflow-gemini-tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "gemini-imagen4-text-to-image.json"
  source = "src/comfyui-workflows/gemini-imagen4-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow-imagen3-tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "imagen3-text-to-image.json"
  source = "src/comfyui-workflows/imagen3-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow-imagen3-veo2-itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "imagen3-veo2-text-to-image-to-video.json"
  source     = "src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.json"
  depends_on = [local_file.workflow-imagen3-veo2-itv]
}

resource "google_storage_bucket_object" "workflow-imagen4-tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "imagen4-text-to-image.json"
  source = "src/comfyui-workflows/imagen4-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow-imagen4-veo3-itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "imagen4-veo3-text-to-image-to-video.json"
  source     = "src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.json"
  depends_on = [local_file.workflow-imagen4-veo3-itv]
}

resource "google_storage_bucket_object" "workflows-ltxv-ttv" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "ltxv-text-to-video.json"
  source = "src/comfyui-workflows/ltxv-text-to-video.json"
}

resource "google_storage_bucket_object" "workflows-sdxl-tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "sdxl-text-to-image.json"
  source = "src/comfyui-workflows/sdxl-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow-veo2-ttv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo2-text-to-video.json"
  source     = "src/comfyui-workflows/veo2-text-to-video.json"
  depends_on = [local_file.workflow-veo2-ttv]
}

resource "google_storage_bucket_object" "workflow-veo3-itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo3-image-to-video.json"
  source     = "src/comfyui-workflows/veo3-image-to-video.json"
  depends_on = [local_file.workflow-veo3-itv]
}

resource "google_storage_bucket_object" "workflow-veo3-ttv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo3-text-to-video.json"
  source     = "src/comfyui-workflows/veo3-text-to-video.json"
  depends_on = [local_file.workflow-veo3-ttv]
}

resource "google_storage_bucket_object" "workflow-vto" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "virtual-try-on.json"
  source     = "src/comfyui-workflows/virtual-try-on.json"
  depends_on = [google_storage_bucket_object.vto-gcsimage]
}


resource "local_file" "workflow-imagen3-veo2-itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.json"
}

resource "local_file" "workflow-imagen4-veo3-itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.json"
}

resource "local_file" "workflow-veo2-ttv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo2-text-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo2-text-to-video.json"
}

resource "local_file" "workflow-veo3-itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo3-image-to-video.tftpl.json",
    {
      input_bucket_uri  = google_storage_bucket.comfyui_input.url
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo3-image-to-video.json"
}

resource "local_file" "workflow-veo3-ttv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo3-text-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo3-text-to-video.json"
}
