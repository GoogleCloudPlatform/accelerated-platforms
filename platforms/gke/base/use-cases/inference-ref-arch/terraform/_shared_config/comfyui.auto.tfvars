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

app_name                     = "comfyui"
accelerator                  = "nvidia-l4"
artifact_repo_name           = "comfyui"
comfyui_kubernetes_namespace = "comfyui-ns"
comfyui_image_name           = "comfyui"
comfyui_image_staging_bucket = "image-staging"
comfyui_image_tag            = "0.0.1"
comfyui_storage_buckets = {
  "comfyui-models" = {
    force_destroy      = true,
    versioning_enabled = false
  },
  "comfyui-input" = {
    force_destroy      = true,
    versioning_enabled = false
  },
  "comfyui-output" = {
    force_destroy      = true,
    versioning_enabled = false
  },
}
iap_domain = ""
