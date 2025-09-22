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

"""Unit tests for helper_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.helper_nodes import (
    VeoVideoToVHSNode,
    VeoVideoSaveAndPreview,
)


class TestHelperNodes(unittest.TestCase):
    """Test cases for helper nodes."""

    def test_veo_video_to_vhs_initialization(self):
        """Test that the VeoVideoToVHSNode can be initialized."""
        node = VeoVideoToVHSNode()
        self.assertIsNotNone(node)

    def test_veo_video_save_and_preview_initialization(self):
        """Test that the VeoVideoSaveAndPreview can be initialized."""
        node = VeoVideoSaveAndPreview()
        self.assertIsNotNone(node)


if __name__ == "__main__":
    unittest.main()