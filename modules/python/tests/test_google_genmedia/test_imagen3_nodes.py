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

"""Unit tests for imagen3_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock
import torch
from PIL import Image

from src.custom_nodes.google_genmedia.imagen3_nodes import Imagen3TextToImageNode
from src.custom_nodes.google_genmedia import exceptions


class TestImagen3TextToImageNode(unittest.TestCase):
    """Test cases for Imagen3TextToImageNode class."""

    def test_initialization(self):
        """Test that the node can be initialized."""
        node = Imagen3TextToImageNode()
        self.assertIsNotNone(node)

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_generate_and_return_image_success(self, mock_imagen3_api):
        """Test a successful run of generate_and_return_image."""
        mock_api_instance = mock_imagen3_api.return_value
        # Create a dummy PIL image
        dummy_pil_image = Image.new("RGB", (64, 64), color="red")
        mock_api_instance.generate_image_from_text.return_value = [dummy_pil_image]

        node = Imagen3TextToImageNode()
        result = node.generate_and_return_image(prompt="a cat")

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], torch.Tensor)

    def test_generate_and_return_image_empty_prompt(self):
        """Test generate_and_return_image with an empty prompt."""
        node = Imagen3TextToImageNode()
        with self.assertRaises(exceptions.ConfigurationError):
            node.generate_and_return_image(prompt="")

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_generate_and_return_image_api_error(self, mock_imagen3_api):
        """Test generate_and_return_image with an API call error."""
        mock_api_instance = mock_imagen3_api.return_value
        mock_api_instance.generate_image_from_text.side_effect = (
            exceptions.APICallError("API Call Error")
        )
        node = Imagen3TextToImageNode()
        with self.assertRaises(exceptions.APICallError):
            node.generate_and_return_image(prompt="a cat")

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_generate_and_return_image_no_images(self, mock_imagen3_api):
        """Test generate_and_return_image with no returned images."""
        mock_api_instance = mock_imagen3_api.return_value
        mock_api_instance.generate_image_from_text.return_value = []
        node = Imagen3TextToImageNode()
        with self.assertRaisesRegex(
            RuntimeError, "Imagen API failed to generate images"
        ):
            node.generate_and_return_image(prompt="a cat")


if __name__ == "__main__":
    unittest.main()
