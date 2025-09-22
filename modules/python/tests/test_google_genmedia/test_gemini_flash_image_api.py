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

"""Unit tests for gemini_flash_image_api.py"""


import unittest
from unittest.mock import MagicMock, Mock, patch

import google.genai.errors as genai_errors_mock
from google.api_core import exceptions as api_core_exceptions_mock


class MockAPIError(Exception):
    pass


class MockGoogleAPICallError(Exception):
    pass


genai_errors_mock.APIError = MockAPIError
api_core_exceptions_mock.GoogleAPICallError = MockGoogleAPICallError


from src.custom_nodes.google_genmedia.exceptions import APICallError

# Now import the specific modules directly
from src.custom_nodes.google_genmedia.gemini_flash_image_api import GeminiFlashImageAPI


class TestGeminiFlashImageAPI(unittest.TestCase):
    """Test cases for GeminiFlashImageAPI class."""

    @patch("src.custom_nodes.google_genmedia.base_api.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.base_api.genai.Client")
    def setUp(self, mock_client, mock_get_metadata):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region = "us-central1"
        self.api = GeminiFlashImageAPI(project_id=self.project_id, region=self.region)
        self.api.client = Mock()

    def test_generate_image_success(self):
        """Test successful image generation."""
        mock_response = MagicMock()
        part = MagicMock()
        part.inline_data.data = b"image_data"
        part.text = None
        mock_response.candidates[0].content.parts = [part]
        self.api.client.models.generate_content.return_value = mock_response
        with patch("PIL.Image.open") as mock_open:
            result = self.api.generate_image(
                model="GEMINI_25_FLASH_IMAGE_PREVIEW",
                prompt="a cat",
                temperature=0.5,
                top_p=0.5,
                top_k=20,
                hate_speech_threshold="BLOCK_NONE",
                harassment_threshold="BLOCK_NONE",
                sexually_explicit_threshold="BLOCK_NONE",
                dangerous_content_threshold="BLOCK_NONE",
                system_instruction="",
            )
            mock_open.assert_called_once()
            self.assertEqual(len(result), 1)

    def test_generate_image_api_error(self):
        """Test that an API error raises an APICallError."""
        self.api.client.models.generate_content.side_effect = (
            genai_errors_mock.APIError("API error")
        )
        with self.assertRaises(APICallError):
            self.api.generate_image(
                model="GEMINI_25_FLASH_IMAGE_PREVIEW",
                prompt="a cat",
                temperature=0.5,
                top_p=0.5,
                top_k=20,
                hate_speech_threshold="BLOCK_NONE",
                harassment_threshold="BLOCK_NONE",
                sexually_explicit_threshold="BLOCK_NONE",
                dangerous_content_threshold="BLOCK_NONE",
                system_instruction="",
            )

    def test_generate_image_no_image_data(self):
        """Test that no image data in the response returns an empty list."""
        mock_response = MagicMock()
        mock_response.candidates[0].content.parts = []
        self.api.client.models.generate_content.return_value = mock_response
        result = self.api.generate_image(
            model="GEMINI_25_FLASH_IMAGE_PREVIEW",
            prompt="a cat",
            temperature=0.5,
            top_p=0.5,
            top_k=20,
            hate_speech_threshold="BLOCK_NONE",
            harassment_threshold="BLOCK_NONE",
            sexually_explicit_threshold="BLOCK_NONE",
            dangerous_content_threshold="BLOCK_NONE",
            system_instruction="",
        )
        self.assertEqual(result, [])

    def test_generate_image_text_instead_of_image(self):
        """Test that text in the response instead of an image returns an empty list."""
        mock_response = MagicMock()
        part = MagicMock()
        part.inline_data.data = None
        part.text = "some text"
        mock_response.candidates[0].content.parts = [part]
        self.api.client.models.generate_content.return_value = mock_response
        result = self.api.generate_image(
            model="GEMINI_25_FLASH_IMAGE_PREVIEW",
            prompt="a cat",
            temperature=0.5,
            top_p=0.5,
            top_k=20,
            hate_speech_threshold="BLOCK_NONE",
            harassment_threshold="BLOCK_NONE",
            sexually_explicit_threshold="BLOCK_NONE",
            dangerous_content_threshold="BLOCK_NONE",
            system_instruction="",
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
