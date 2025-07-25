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

# This is a preview version of Google GenAI custom nodes

from enum import Enum

from google.genai import types

AUDIO_MIME_TYPES = ["audio/mp3", "audio/wav", "audio/mpeg"]
GEMINI_USER_AGENT = "cloud-solutions/comfyui-gemini-custom-node-v1"
IMAGE_MIME_TYPES = ["image/png", "image/jpeg"]
IMAGEN3_MODEL_ID = "imagen-3.0-generate-002"
IMAGEN3_USER_AGENT = "cloud-solutions/comfyui-imagen3-custom-node-v1"
IMAGEN4_USER_AGENT = "cloud-solutions/comfyui-imagen4-custom-node-v1"
MAX_SEED = 0xFFFFFFFF
STORAGE_USER_AGENT = "cloud-solutions/comfyui-gcs-custom-node-v1"
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".mkv"}
VEO2_MODEL_ID = "veo-2.0-generate-001"
VEO2_USER_AGENT = "cloud-solutions/comfyui-veo2-custom-node-v1"
VEO3_USER_AGENT = "cloud-solutions/comfyui-veo3-custom-node-v1"
VIDEO_MIME_TYPES = ["video/mp4", "video/mpeg"]


class GeminiModel(Enum):
    GEMINI_PRO = "gemini-2.5-pro"
    GEMINI_FLASH = "gemini-2.5-flash"
    GEMINI_FLASH_LITE = "gemini-2.5-flash-lite-preview-06-17"


class Imagen4Model(str, Enum):
    IMAGEN_4_PREVIEW = "imagen-4.0-generate-preview-06-06"
    IMAGEN_4_FAST_PREVIEW = "imagen-4.0-fast-generate-preview-06-06"
    IMAGEN_4_ULTRA_PREVIEW = "imagen-4.0-ultra-generate-preview-06-06"


class ThresholdOptions(Enum):
    BLOCK_NONE = types.HarmBlockThreshold.BLOCK_NONE
    BLOCK_ONLY_HIGH = types.HarmBlockThreshold.BLOCK_ONLY_HIGH
    BLOCK_MEDIUM_AND_ABOVE = types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    BLOCK_LOW_AND_ABOVE = types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE


class Veo3Model(str, Enum):
    VEO_3_PREVIEW = "veo-3.0-generate-preview"
    VEO_3_FAST_PREVIEW = "veo-3.0-fast-generate-preview"
