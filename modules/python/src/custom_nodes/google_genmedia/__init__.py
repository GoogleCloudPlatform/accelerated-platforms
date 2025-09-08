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

import os

from .gemini_nodes import NODE_CLASS_MAPPINGS as GEMINI_NODE_CLASS_MAPPINGS
from .gemini_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
)
from .helper_nodes import NODE_CLASS_MAPPINGS as HELPER_NODE_CLASS_MAPPINGS
from .helper_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as HELPER_NODE_DISPLAY_NAME_MAPPINGS,
)
from .imagen3_nodes import NODE_CLASS_MAPPINGS as IMAGEN3_NODE_CLASS_MAPPINGS
from .imagen3_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
)
from .imagen4_nodes import NODE_CLASS_MAPPINGS as IMAGEN4_NODE_CLASS_MAPPINGS
from .imagen4_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
)
from .veo2_nodes import NODE_CLASS_MAPPINGS as VEO2_NODE_CLASS_MAPPINGS
from .veo2_nodes import NODE_DISPLAY_NAME_MAPPINGS as VEO2_NODE_DISPLAY_NAME_MAPPINGS
from .veo3_nodes import NODE_CLASS_MAPPINGS as VEO3_NODE_CLASS_MAPPINGS
from .veo3_nodes import NODE_DISPLAY_NAME_MAPPINGS as VEO3_NODE_DISPLAY_NAME_MAPPINGS
from .virtual_try_on import NODE_CLASS_MAPPINGS as VTO_NODE_CLASS_MAPPINGS
from .virtual_try_on import NODE_DISPLAY_NAME_MAPPINGS as VTO_NODE_DISPLAY_NAME_MAPPINGS
from .gemini_flash_image_node import (
    NODE_CLASS_MAPPINGS as GEMINI_FLASH_25_IMAGE_NODE_CLASS_MAPPINGS,
)
from .gemini_flash_image_node import (
    NODE_DISPLAY_NAME_MAPPINGS as GEMINI_FLASH_25_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
)


# Combine all node class mappings
NODE_CLASS_MAPPINGS = {
    **IMAGEN3_NODE_CLASS_MAPPINGS,
    **IMAGEN4_NODE_CLASS_MAPPINGS,
    **VEO2_NODE_CLASS_MAPPINGS,
    **VEO3_NODE_CLASS_MAPPINGS,
    **GEMINI_NODE_CLASS_MAPPINGS,
    **HELPER_NODE_CLASS_MAPPINGS,
    **VTO_NODE_CLASS_MAPPINGS,
    **GEMINI_FLASH_25_IMAGE_NODE_CLASS_MAPPINGS,
}

# Combine all node display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    **IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
    **IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
    **VEO2_NODE_DISPLAY_NAME_MAPPINGS,
    **VEO3_NODE_DISPLAY_NAME_MAPPINGS,
    **GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
    **HELPER_NODE_DISPLAY_NAME_MAPPINGS,
    **VTO_NODE_DISPLAY_NAME_MAPPINGS,
    **GEMINI_FLASH_25_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
