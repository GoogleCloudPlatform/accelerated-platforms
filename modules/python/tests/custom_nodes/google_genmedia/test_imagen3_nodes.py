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

import unittest
from unittest.mock import patch, MagicMock
import torch
from PIL import Image
import sys
from unittest.mock import MagicMock

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.imagen3_nodes import Imagen3TextToImageNode


class TestImagen3TextToImageNode(unittest.TestCase):
    def setUp(self):
        self.node = Imagen3TextToImageNode()

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_generate_and_return_image_success(self, mock_imagen_api):
        # Arrange
        mock_api_instance = MagicMock()
        mock_pil_image = Image.new("RGB", (1024, 1024))
        mock_api_instance.generate_image_from_text.return_value = [mock_pil_image]
        mock_imagen_api.return_value = mock_api_instance

        # Act
        (result_tensor,) = self.node.generate_and_return_image(
            prompt="a test prompt", number_of_images=1
        )

        # Assert
        self.assertIsInstance(result_tensor, torch.Tensor)
        self.assertEqual(result_tensor.shape, (1, 1024, 1024, 3))
        mock_imagen_api.assert_called_once()
        mock_api_instance.generate_image_from_text.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_generate_and_return_image_api_failure(self, mock_imagen_api):
        # Arrange
        mock_api_instance = MagicMock()
        mock_api_instance.generate_image_from_text.return_value = (
            []
        )  # No images returned
        mock_imagen_api.return_value = mock_api_instance

        # Act & Assert
        with self.assertRaisesRegex(
            RuntimeError, "Imagen API failed to generate images"
        ):
            self.node.generate_and_return_image(
                prompt="a test prompt", number_of_images=1
            )

    @patch("src.custom_nodes.google_genmedia.imagen3_nodes.Imagen3API")
    def test_init_failure(self, mock_imagen_api):
        # Arrange
        mock_imagen_api.side_effect = Exception("Init failed")

        # Act & Assert
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize Imagen API"):
            self.node.generate_and_return_image(prompt="a test prompt")


if __name__ == "__main__":
    unittest.main()
