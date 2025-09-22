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

"""Unit tests for gemini_flash_image_node.py"""

import unittest
from unittest.mock import patch, MagicMock
import torch
from PIL import Image

from src.custom_nodes.google_genmedia.gemini_flash_image_node import Gemini25FlashImage
from src.custom_nodes.google_genmedia import exceptions


class TestGemini25FlashImage(unittest.TestCase):
    """Test cases for Gemini25FlashImage class."""

    def test_initialization(self):
        """Test that the node can be initialized."""
        node = Gemini25FlashImage()
        self.assertIsNotNone(node)

    @patch(
        "src.custom_nodes.google_genmedia.gemini_flash_image_node.GeminiFlashImageAPI"
    )
    def test_generate_and_return_image_success(self, mock_gemini_flash_image_api):
        """Test a successful run of generate_and_return_image."""
        mock_api_instance = mock_gemini_flash_image_api.return_value
        # Create a dummy PIL image
        dummy_pil_image = Image.new("RGB", (64, 64), color="red")
        mock_api_instance.generate_image.return_value = [dummy_pil_image]

        node = Gemini25FlashImage()
        result = node.generate_and_return_image(
            model="GEMINI_25_FLASH_IMAGE_PREVIEW",
            prompt="a cat",
            temperature=0.7,
            top_p=1.0,
            top_k=32,
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
            system_instruction="",
        )

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], torch.Tensor)

    @patch(
        "src.custom_nodes.google_genmedia.gemini_flash_image_node.GeminiFlashImageAPI",
        side_effect=exceptions.APIInitializationError("API Init Error"),
    )
    def test_generate_and_return_image_init_error(self, mock_gemini_flash_image_api):
        """Test generate_and_return_image with an API initialization error."""
        node = Gemini25FlashImage()
        with self.assertRaisesRegex(
            RuntimeError, "Failed to initialize Imagen API client"
        ):
            node.generate_and_return_image(
                model="GEMINI_25_FLASH_IMAGE_PREVIEW",
                prompt="a cat",
                temperature=0.7,
                top_p=1.0,
                top_k=32,
                hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
                harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
                sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
                dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
                system_instruction="",
            )

    @patch(
        "src.custom_nodes.google_genmedia.gemini_flash_image_node.GeminiFlashImageAPI"
    )
    def test_generate_and_return_image_api_error(self, mock_gemini_flash_image_api):
        """Test generate_and_return_image with an API call error."""
        mock_api_instance = mock_gemini_flash_image_api.return_value
        mock_api_instance.generate_image.side_effect = exceptions.APICallError(
            "API Call Error"
        )
        node = Gemini25FlashImage()
        with self.assertRaisesRegex(
            RuntimeError, "Error occurred during image generation"
        ):
            node.generate_and_return_image(
                model="GEMINI_25_FLASH_IMAGE_PREVIEW",
                prompt="a cat",
                temperature=0.7,
                top_p=1.0,
                top_k=32,
                hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
                harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
                sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
                dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
                system_instruction="",
            )

    @patch(
        "src.custom_nodes.google_genmedia.gemini_flash_image_node.GeminiFlashImageAPI"
    )
    def test_generate_and_return_image_no_images(self, mock_gemini_flash_image_api):
        """Test generate_and_return_image with no returned images."""
        mock_api_instance = mock_gemini_flash_image_api.return_value
        mock_api_instance.generate_image.return_value = []
        node = Gemini25FlashImage()
        with self.assertRaisesRegex(
            RuntimeError, "Imagen API failed to generate images"
        ):
            node.generate_and_return_image(
                model="GEMINI_25_FLASH_IMAGE_PREVIEW",
                prompt="a cat",
                temperature=0.7,
                top_p=1.0,
                top_k=32,
                hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
                harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
                sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
                dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
                system_instruction="",
            )


if __name__ == "__main__":
    unittest.main()
