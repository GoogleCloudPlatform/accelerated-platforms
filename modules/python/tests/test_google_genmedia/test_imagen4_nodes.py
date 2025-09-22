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

"""Unit tests for imagen4_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock
import torch
from PIL import Image

from src.custom_nodes.google_genmedia.imagen4_nodes import Imagen4TextToImageNode
from src.custom_nodes.google_genmedia import exceptions


class TestImagen4TextToImageNode(unittest.TestCase):
    """Test cases for Imagen4TextToImageNode class."""

    def test_initialization(self):
        """Test that the node can be initialized."""
        node = Imagen4TextToImageNode()
        self.assertIsNotNone(node)

    @patch("src.custom_nodes.google_genmedia.imagen4_nodes.Imagen4API")
    def test_generate_and_return_image_success(self, mock_imagen4_api):
        """Test a successful run of generate_and_return_image."""
        mock_api_instance = mock_imagen4_api.return_value
        # Create a dummy PIL image
        dummy_pil_image = Image.new("RGB", (64, 64), color="red")
        mock_api_instance.generate_image_from_text.return_value = [dummy_pil_image]

        node = Imagen4TextToImageNode()
        result = node.generate_and_return_image(prompt="a cat")

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], torch.Tensor)

    @patch(
        "src.custom_nodes.google_genmedia.imagen4_nodes.Imagen4API",
        side_effect=exceptions.APIInitializationError("API Init Error"),
    )
    def test_generate_and_return_image_init_error(self, mock_imagen4_api):
        """Test generate_and_return_image with an API initialization error."""
        node = Imagen4TextToImageNode()
        with self.assertRaisesRegex(
            RuntimeError, "Failed to initialize Imagen API client"
        ):
            node.generate_and_return_image(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.imagen4_nodes.Imagen4API")
    def test_generate_and_return_image_api_error(self, mock_imagen4_api):
        """Test generate_and_return_image with an API call error."""
        mock_api_instance = mock_imagen4_api.return_value
        mock_api_instance.generate_image_from_text.side_effect = (
            exceptions.APICallError("API Call Error")
        )
        node = Imagen4TextToImageNode()
        with self.assertRaisesRegex(
            RuntimeError, "Error occurred during image generation"
        ):
            node.generate_and_return_image(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.imagen4_nodes.Imagen4API")
    def test_generate_and_return_image_no_images(self, mock_imagen4_api):
        """Test generate_and_return_image with no returned images."""
        mock_api_instance = mock_imagen4_api.return_value
        mock_api_instance.generate_image_from_text.return_value = []
        node = Imagen4TextToImageNode()
        with self.assertRaisesRegex(
            RuntimeError, "Imagen API failed to generate images"
        ):
            node.generate_and_return_image(prompt="a cat")


if __name__ == "__main__":
    unittest.main()
