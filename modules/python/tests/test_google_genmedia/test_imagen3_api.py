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

"""Unit tests for imagen3_api.py"""
import unittest
from unittest.mock import Mock, patch

from src.custom_nodes.google_genmedia.exceptions import ConfigurationError
from src.custom_nodes.google_genmedia.imagen3_api import Imagen3API


class TestImagen3API(unittest.TestCase):
    """Test cases for Imagen3API class."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region = "us-central1"
        with patch(
            "src.custom_nodes.google_genmedia.base_api.GoogleGenAIBaseAPI.__init__",
            return_value=None,
        ):
            self.api = Imagen3API(project_id=self.project_id, region=self.region)
            self.api.client = Mock()

    @patch("src.custom_nodes.google_genmedia.utils.generate_image_from_text")
    def test_generate_image_from_text_success_png(self, mock_generate_image):
        """Test successful image generation with PNG output."""
        self.api.generate_image_from_text(
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
        mock_generate_image.assert_called_once_with(
            client=self.api.client,
            model="imagen-3.0-generate-002",
            prompt="a cat",
            person_generation="allow",
            aspect_ratio="1:1",
            number_of_images=1,
            negative_prompt="",
            seed=123,
            enhance_prompt=False,
            add_watermark=False,
            output_image_type="image/png",
            safety_filter_level="block_most",
        )

    @patch("src.custom_nodes.google_genmedia.utils.generate_image_from_text")
    def test_generate_image_from_text_success_jpeg(self, mock_generate_image):
        """Test successful image generation with JPEG output."""
        self.api.generate_image_from_text(
            prompt="a dog",
            person_generation="dont_allow",
            aspect_ratio="16:9",
            number_of_images=2,
            negative_prompt="blurry",
            seed=456,
            enhance_prompt=True,
            add_watermark=False,
            output_image_type="JPEG",
            safety_filter_level="block_few",
        )
        mock_generate_image.assert_called_once_with(
            client=self.api.client,
            model="imagen-3.0-generate-002",
            prompt="a dog",
            person_generation="dont_allow",
            aspect_ratio="16:9",
            number_of_images=2,
            negative_prompt="blurry",
            seed=456,
            enhance_prompt=True,
            add_watermark=False,
            output_image_type="image/jpeg",
            safety_filter_level="block_few",
        )

    def test_generate_image_from_text_empty_prompt(self):
        """Test that an empty prompt raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError) as context:
            self.api.generate_image_from_text(
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
        self.assertEqual(str(context.exception), "Prompt cannot be empty.")

    def test_generate_image_from_text_invalid_number_of_images(self):
        """Test that an invalid number of images raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError) as context:
            self.api.generate_image_from_text(
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
        self.assertEqual(
            str(context.exception), "Number of images 5 must be between 1 and 4."
        )

    def test_generate_image_from_text_seed_with_watermark(self):
        """Test that using a seed with a watermark raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError) as context:
            self.api.generate_image_from_text(
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
        self.assertEqual(
            str(context.exception),
            "Seed is not supported when add_watermark is enabled.",
        )

    def test_generate_image_from_text_empty_output_image_type(self):
        """Test that an empty output image type raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError) as context:
            self.api.generate_image_from_text(
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="",
                safety_filter_level="block_most",
            )
        self.assertEqual(str(context.exception), "Output image type cannot be empty.")

    def test_generate_image_from_text_unsupported_output_image_type(self):
        """Test that an unsupported output image type raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError) as context:
            self.api.generate_image_from_text(
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
        self.assertEqual(str(context.exception), "Unsupported image format: GIF")


if __name__ == "__main__":
    unittest.main()
