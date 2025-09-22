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

"""Unit tests for veo2_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock
import torch

from src.custom_nodes.google_genmedia.veo2_nodes import (
    Veo2TextToVideoNode,
    Veo2GcsUriImageToVideoNode,
    Veo2ImageToVideoNode,
)
from src.custom_nodes.google_genmedia import exceptions


class TestVeo2Nodes(unittest.TestCase):
    """Test cases for Veo2 nodes."""

    def test_text_to_video_initialization(self):
        """Test that the Veo2TextToVideoNode can be initialized."""
        node = Veo2TextToVideoNode()
        self.assertIsNotNone(node)

    def test_gcs_uri_image_to_video_initialization(self):
        """Test that the Veo2GcsUriImageToVideoNode can be initialized."""
        node = Veo2GcsUriImageToVideoNode()
        self.assertIsNotNone(node)

    def test_image_to_video_initialization(self):
        """Test that the Veo2ImageToVideoNode can be initialized."""
        node = Veo2ImageToVideoNode()
        self.assertIsNotNone(node)

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_text_to_video_generate_success(self, mock_veo2_api):
        """Test a successful run of Veo2TextToVideoNode.generate."""
        mock_api_instance = mock_veo2_api.return_value
        mock_api_instance.generate_video_from_text.return_value = ["video_path"]
        node = Veo2TextToVideoNode()
        result = node.generate(prompt="a cat")
        self.assertEqual(result, (["video_path"],))

    @patch(
        "src.custom_nodes.google_genmedia.veo2_nodes.Veo2API",
        side_effect=exceptions.APIInitializationError("API Init Error"),
    )
    def test_text_to_video_generate_init_error(self, mock_veo2_api):
        """Test Veo2TextToVideoNode.generate with an API initialization error."""
        node = Veo2TextToVideoNode()
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize Veo API"):
            node.generate(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_text_to_video_generate_api_error(self, mock_veo2_api):
        """Test Veo2TextToVideoNode.generate with an API call error."""
        mock_api_instance = mock_veo2_api.return_value
        mock_api_instance.generate_video_from_text.side_effect = (
            exceptions.APICallError("API Call Error")
        )
        node = Veo2TextToVideoNode()
        with self.assertRaisesRegex(RuntimeError, "Video generation error"):
            node.generate(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_gcs_uri_image_to_video_generate_success(self, mock_veo2_api):
        """Test a successful run of Veo2GcsUriImageToVideoNode.generate."""
        mock_api_instance = mock_veo2_api.return_value
        mock_api_instance.generate_video_from_gcsuri_image.return_value = ["video_path"]
        node = Veo2GcsUriImageToVideoNode()
        result = node.generate(gcsuri="gs://bucket/image.png", prompt="a cat")
        self.assertEqual(result, (["video_path"],))

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_image_to_video_generate_success(self, mock_veo2_api):
        """Test a successful run of Veo2ImageToVideoNode.generate."""
        mock_api_instance = mock_veo2_api.return_value
        mock_api_instance.generate_video_from_image.return_value = ["video_path"]
        node = Veo2ImageToVideoNode()
        # Create a dummy tensor for the image
        dummy_image = torch.zeros(1, 64, 64, 3)
        result = node.generate(image=dummy_image, prompt="a cat")
        self.assertEqual(result, (["video_path"],))


if __name__ == "__main__":
    unittest.main()
