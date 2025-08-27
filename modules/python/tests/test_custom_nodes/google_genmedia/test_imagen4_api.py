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
import sys
from unittest.mock import MagicMock

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.imagen4_api import Imagen4API, Imagen4Model
from PIL import Image


class TestImagen4API(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.imagen4_api.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.imagen4_api.genai.Client")
    def setUp(self, mock_genai_client, mock_get_gcp_metadata):
        mock_get_gcp_metadata.side_effect = ["test-project", "us-central1"]
        self.mock_client = MagicMock()
        mock_genai_client.return_value = self.mock_client
        self.api = Imagen4API(project_id="test-project", region="us-central1")

    @patch(
        "src.custom_nodes.google_genmedia.imagen4_api.utils.generate_image_from_text"
    )
    def test_generate_image_from_text_success(self, mock_generate):
        # Arrange
        mock_image = Image.new("RGB", (100, 100))
        mock_generate.return_value = [mock_image]

        # Act
        images = self.api.generate_image_from_text(
            model=Imagen4Model.IMAGEN_4_PREVIEW.name,
            prompt="a cat",
            person_generation="ALLOW_ADULT",
            aspect_ratio="1:1",
            number_of_images=1,
            negative_prompt="",
            seed=123,
            enhance_prompt=False,
            add_watermark=False,
            output_image_type="PNG",
            safety_filter_level="BLOCK_LOW_AND_ABOVE",
        )

        # Assert
        self.assertEqual(len(images), 1)
        self.assertIsInstance(images[0], Image.Image)
        mock_generate.assert_called_once()

    def test_generate_image_from_text_ultra_model_multiple_images(self):
        with self.assertRaises(ValueError):
            self.api.generate_image_from_text(
                model=Imagen4Model.IMAGEN_4_ULTRA_PREVIEW.name,
                prompt="a cat",
                person_generation="ALLOW_ADULT",
                aspect_ratio="1:1",
                number_of_images=2,  # Invalid for ultra
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
            )

    @patch(
        "src.custom_nodes.google_genmedia.imagen4_api.utils.generate_image_from_text"
    )
    def test_generate_image_from_text_api_failure(self, mock_generate):
        # Arrange
        mock_generate.side_effect = RuntimeError("API Error")

        # Act & Assert
        with self.assertRaises(RuntimeError):
            self.api.generate_image_from_text(
                model=Imagen4Model.IMAGEN_4_PREVIEW.name,
                prompt="a cat",
                person_generation="ALLOW_ADULT",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
            )


if __name__ == "__main__":
    unittest.main()
