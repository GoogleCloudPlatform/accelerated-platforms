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

"""Unit tests for imagen4_api.py"""
import unittest
from unittest.mock import Mock, patch

from src.custom_nodes.google_genmedia.exceptions import ConfigurationError

# Now import the specific modules directly
from src.custom_nodes.google_genmedia.imagen4_api import Imagen4API


class TestImagen4API(unittest.TestCase):
    """Test cases for Imagen4API class."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region = "us-central1"
        with patch(
            "src.custom_nodes.google_genmedia.base_api.GoogleGenAIBaseAPI.__init__",
            return_value=None,
        ):
            self.api = Imagen4API(project_id=self.project_id, region=self.region)
            self.api.client = Mock()

    @patch("src.custom_nodes.google_genmedia.utils.generate_image_from_text")
    def test_generate_image_from_text_success(self, mock_generate_image):
        """Test successful image generation from text."""
        self.api.generate_image_from_text(
            model="IMAGEN_4_PREVIEW",
            prompt="a cat",
            person_generation="allow",
            aspect_ratio="1:1",
            number_of_images=1,
            negative_prompt="",
            seed=123,
            enhance_prompt=False,
            add_watermark=False,
            output_image_type="PNG",
            safety_filter_level="block_most",
        )
        mock_generate_image.assert_called_once()

    def test_generate_image_from_text_empty_prompt(self):
        """Test that an empty prompt raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_image_from_text(
                model="IMAGEN_4_PREVIEW",
                prompt="",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )

    def test_generate_image_from_text_invalid_number_of_images(self):
        """Test that an invalid number of images raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_image_from_text(
                model="IMAGEN_4_PREVIEW",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=5,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )

    def test_generate_image_from_text_seed_with_watermark(self):
        """Test that using a seed with a watermark raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_image_from_text(
                model="IMAGEN_4_PREVIEW",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=True,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )

    def test_generate_image_from_text_unsupported_output_image_type(self):
        """Test that an unsupported output image type raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_image_from_text(
                model="IMAGEN_4_PREVIEW",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="GIF",
                safety_filter_level="block_most",
            )

    def test_generate_image_from_text_ultra_model_invalid_number_of_images(self):
        """Test that the ultra model with an invalid number of images raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_image_from_text(
                model="IMAGEN_4_ULTRA_PREVIEW",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=5,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )


if __name__ == "__main__":
    unittest.main()
