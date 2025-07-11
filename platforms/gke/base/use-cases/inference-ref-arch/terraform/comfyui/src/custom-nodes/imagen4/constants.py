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

# This is a preview version of imagen4 custom node

from enum import Enum

MAX_SEED = 0xFFFFFFFF
USER_AGENT = "cloud-solutions/comfyui-imagen4-custom-node-v1"


class Imagen4Model(str, Enum):
    IMAGEN_4_PREVIEW = "imagen-4.0-generate-preview-06-06"
    IMAGEN_4_FAST_PREVIEW = "imagen-4.0-fast-generate-preview-06-06"
    IMAGEN_4_ULTRA_PREVIEW = "imagen-4.0-ultra-generate-preview-06-06"
