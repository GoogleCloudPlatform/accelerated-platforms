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

# This is a preview version of veo3 custom node

from enum import Enum

MAX_SEED = 0xFFFFFFFF
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".mkv"}
USER_AGENT = "cloud-solutions/comfyui-veo3-custom-node-v1"


class Veo3Model(str, Enum):
    VEO_3_PREVIEW = "veo-3.0-generate-preview"
    VEO_3_FAST_PREVIEW = "veo-3.0-fast-generate-preview"
