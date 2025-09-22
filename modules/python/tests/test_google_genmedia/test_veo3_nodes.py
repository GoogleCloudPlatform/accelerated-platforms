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
import torch

from src.custom_nodes.google_genmedia.veo3_nodes import (
    Veo3TextToVideoNode,
    Veo3GcsUriImageToVideoNode,
    Veo3ImageToVideoNode,
)
from src.custom_nodes.google_genmedia import exceptions


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

    @patch("src.custom_nodes.google_genmedia.veo3_nodes.Veo3API")
    def test_text_to_video_generate_success(self, mock_veo3_api):
        """Test a successful run of Veo3TextToVideoNode.generate."""
        mock_api_instance = mock_veo3_api.return_value
        mock_api_instance.generate_video_from_text.return_value = ["video_path"]
        node = Veo3TextToVideoNode()
        result = node.generate(prompt="a cat")
        self.assertEqual(result, (["video_path"],))

    @patch(
        "src.custom_nodes.google_genmedia.veo3_nodes.Veo3API",
        side_effect=exceptions.APIInitializationError("API Init Error"),
    )
    def test_text_to_video_generate_init_error(self, mock_veo3_api):
        """Test Veo3TextToVideoNode.generate with an API initialization error."""
        node = Veo3TextToVideoNode()
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize Veo API"):
            node.generate(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.veo3_nodes.Veo3API")
    def test_text_to_video_generate_api_error(self, mock_veo3_api):
        """Test Veo3TextToVideoNode.generate with an API call error."""
        mock_api_instance = mock_veo3_api.return_value
        mock_api_instance.generate_video_from_text.side_effect = (
            exceptions.APICallError("API Call Error")
        )
        node = Veo3TextToVideoNode()
        with self.assertRaisesRegex(RuntimeError, "Video generation error"):
            node.generate(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.veo3_nodes.Veo3API")
    def test_gcs_uri_image_to_video_generate_success(self, mock_veo3_api):
        """Test a successful run of Veo3GcsUriImageToVideoNode.generate."""
        mock_api_instance = mock_veo3_api.return_value
        mock_api_instance.generate_video_from_gcsuri_image.return_value = ["video_path"]
        node = Veo3GcsUriImageToVideoNode()
        result = node.generate(gcsuri="gs://bucket/image.png", prompt="a cat")
        self.assertEqual(result, (["video_path"],))

    @patch("src.custom_nodes.google_genmedia.veo3_nodes.Veo3API")
    def test_image_to_video_generate_success(self, mock_veo3_api):
        """Test a successful run of Veo3ImageToVideoNode.generate."""
        mock_api_instance = mock_veo3_api.return_value
        mock_api_instance.generate_video_from_image.return_value = ["video_path"]
        node = Veo3ImageToVideoNode()
        # Create a dummy tensor for the image
        dummy_image = torch.zeros(1, 64, 64, 3)
        result = node.generate(image=dummy_image, prompt="a cat")
        self.assertEqual(result, (["video_path"],))


if __name__ == "__main__":
    unittest.main()
