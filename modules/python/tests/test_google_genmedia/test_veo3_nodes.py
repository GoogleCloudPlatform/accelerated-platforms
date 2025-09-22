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

"""Unit tests for veo3_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.veo3_nodes import (
    Veo3TextToVideoNode,
    Veo3GcsUriImageToVideoNode,
    Veo3ImageToVideoNode,
)


class TestVeo3Nodes(unittest.TestCase):
    """Test cases for Veo3 nodes."""

    def test_text_to_video_initialization(self):
        """Test that the Veo3TextToVideoNode can be initialized."""
        node = Veo3TextToVideoNode()
        self.assertIsNotNone(node)

    def test_gcs_uri_image_to_video_initialization(self):
        """Test that the Veo3GcsUriImageToVideoNode can be initialized."""
        node = Veo3GcsUriImageToVideoNode()
        self.assertIsNotNone(node)

    def test_image_to_video_initialization(self):
        """Test that the Veo3ImageToVideoNode can be initialized."""
        node = Veo3ImageToVideoNode()
        self.assertIsNotNone(node)


if __name__ == "__main__":
    unittest.main()