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
  vto_source_path               = "${path.module}/src/comfyui-workflows/input-images/virtual-try-on"
  vto_files_to_upload           = fileset(local.vto_source_path, "**/*.png")
  interpolation_source_path     = "${path.module}/src/comfyui-workflows/input-images/interpolation"
  interpolation_files_to_upload = fileset(local.interpolation_source_path, "**/*.png")
  nano_banana_source_path       = "${path.module}/src/comfyui-workflows/input-images/nano-banana"
  nano_banana_files_to_upload   = fileset(local.nano_banana_source_path, "**/*.png")
  veo_source_path               = "${path.module}/src/comfyui-workflows/input-images/veo"
  veo_files_to_upload           = fileset(local.veo_source_path, "**/*.png")
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

resource "google_storage_bucket_object" "intpl_gcsimage" {
  for_each = local.interpolation_files_to_upload
  bucket   = google_storage_bucket.comfyui_input.name
  name     = "interpolation/${each.key}"
  source   = "${local.interpolation_source_path}/${each.key}"
}

resource "google_storage_bucket_object" "nano_banana_gcsimage" {
  for_each = local.nano_banana_files_to_upload
  bucket   = google_storage_bucket.comfyui_input.name
  name     = "nano-banana/${each.key}"
  source   = "${local.nano_banana_source_path}/${each.key}"
}

resource "google_storage_bucket_object" "veo_gcsimage" {
  for_each = local.veo_files_to_upload
  bucket   = google_storage_bucket.comfyui_input.name
  name     = "veo/${each.key}"
  source   = "${local.veo_source_path}/${each.key}"
}

resource "google_storage_bucket_object" "vto_gcsimage" {
  for_each = local.vto_files_to_upload
  bucket   = google_storage_bucket.comfyui_input.name
  name     = "virtual-try-on/${each.key}"
  source   = "${local.vto_source_path}/${each.key}"
}

resource "google_storage_bucket_object" "workflow_gemini_tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "gemini-imagen4-text-to-image.json"
  source = "src/comfyui-workflows/gemini-imagen4-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow_imagen3_tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "imagen3-text-to-image.json"
  source = "src/comfyui-workflows/imagen3-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow_imagen3_veo2_itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "imagen3-veo2-text-to-image-to-video.json"
  source     = "src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.json"
  depends_on = [local_file.workflow_imagen3_veo2_itv]
}

resource "google_storage_bucket_object" "workflow_imagen4_banana_veo3_interpolation_video" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "imagen4-banana-veo3-interpolation-video.json"
  source = "src/comfyui-workflows/imagen4-banana-veo3-interpolation-video.json"
}

resource "google_storage_bucket_object" "workflow_imagen4_tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "imagen4-text-to-image.json"
  source = "src/comfyui-workflows/imagen4-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow_imagen4_veo3_itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "imagen4-veo3-text-to-image-to-video.json"
  source     = "src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.json"
  depends_on = [local_file.workflow_imagen4_veo3_itv]
}

resource "google_storage_bucket_object" "workflow_intpl_veo3_itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "interpolation-veo3-image-to-video.json"
  source     = "src/comfyui-workflows/interpolation-veo3-image-to-video.json"
  depends_on = [google_storage_bucket_object.intpl_gcsimage]
}

resource "google_storage_bucket_object" "workflows_ltxv_ttv" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "ltxv-text-to-video.json"
  source = "src/comfyui-workflows/ltxv-text-to-video.json"
}

resource "google_storage_bucket_object" "workflow_nano_banana_i2v" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "nano-banana.json"
  source     = "src/comfyui-workflows/nano-banana.json"
  depends_on = [google_storage_bucket_object.nano_banana_gcsimage]
}

resource "google_storage_bucket_object" "workflows_sdxl_tti" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "sdxl-text-to-image.json"
  source = "src/comfyui-workflows/sdxl-text-to-image.json"
}

resource "google_storage_bucket_object" "workflow_veo2_ttv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo2-text-to-video.json"
  source     = "src/comfyui-workflows/veo2-text-to-video.json"
  depends_on = [local_file.workflow_veo2_ttv]
}

resource "google_storage_bucket_object" "workflow_veo3_itv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo3-image-to-video.json"
  source     = "src/comfyui-workflows/veo3-image-to-video.json"
  depends_on = [local_file.workflow_veo3_itv]
}

resource "google_storage_bucket_object" "workflow_veo3_r2v" {
  bucket = google_storage_bucket.comfyui_workflow.name
  name   = "veo3-reference-to-video.json"
  source = "src/comfyui-workflows/veo3-reference-to-video.json"
}

resource "google_storage_bucket_object" "workflow_veo3_ttv" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "veo3-text-to-video.json"
  source     = "src/comfyui-workflows/veo3-text-to-video.json"
  depends_on = [local_file.workflow_veo3_ttv]
}

resource "google_storage_bucket_object" "workflow_vto" {
  bucket     = google_storage_bucket.comfyui_workflow.name
  name       = "virtual-try-on.json"
  source     = "src/comfyui-workflows/virtual-try-on.json"
  depends_on = [google_storage_bucket_object.vto_gcsimage]
}


resource "local_file" "workflow_imagen3_veo2_itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/imagen3-veo2-text-to-image-to-video.json"
}

resource "local_file" "workflow_imagen4_veo3_itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/imagen4-veo3-text-to-image-to-video.json"
}

resource "local_file" "workflow_veo2_ttv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo2-text-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo2-text-to-video.json"
}

resource "local_file" "workflow_veo3_itv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo3-image-to-video.tftpl.json",
    {
      input_bucket_uri  = google_storage_bucket.comfyui_input.url
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo3-image-to-video.json"
}

resource "local_file" "workflow_veo3_ttv" {
  content = templatefile(
    "${path.module}/src/comfyui-workflows/veo3-text-to-video.tftpl.json",
    {
      output_bucket_uri = google_storage_bucket.comfyui_output.url
    }
  )
  filename = "${path.module}/src/comfyui-workflows/veo3-text-to-video.json"
}
