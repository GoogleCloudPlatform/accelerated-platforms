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

"""Unit tests for gemini_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.gemini_nodes import GeminiNode25
from src.custom_nodes.google_genmedia import exceptions


class TestGeminiNode25(unittest.TestCase):
    """Test cases for GeminiNode25 class."""

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
    def setUp(self, mock_genai_client, mock_get_gcp_metadata):
        """Set up test fixtures."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        self.node = GeminiNode25()
        self.node.client = mock_genai_client

    def test_initialization(self):
        """Test that the node can be initialized."""
        self.assertIsNotNone(self.node)

    def test_generate_content_empty_prompt(self):
        """Test generate_content with an empty prompt."""
        result = self.node.generate_content(
            prompt="",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertEqual(result, ("Error: Prompt cannot be empty.",))

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
        side_effect=exceptions.APIInitializationError("Test Error"),
    )
    def test_generate_content_reinitialization_error(self, mock_init):
        """Test generate_content with a re-initialization error."""
        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
            gcp_project_id="new_project",
        )
        self.assertIn("Error re-initializing Gemini client", result[0])

    @patch(
        "src.custom_nodes.google_genmedia.utils.prep_for_media_conversion",
        return_value=None,
    )
    def test_generate_content_success(self, mock_prep_media):
        """Test a successful run of generate_content."""
        mock_response = MagicMock()
        mock_response.candidates[0].content.parts[0].text = "Generated text"
        self.node._generate_content = MagicMock(return_value=mock_response)

        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertEqual(result, ("Generated text",))

    @patch("src.custom_nodes.google_genmedia.utils.prep_for_media_conversion")
    def test_generate_content_with_image(self, mock_prep_media):
        """Test generate_content with an image."""
        mock_prep_media.return_value = "image_part"
        mock_response = MagicMock()
        mock_response.candidates[0].content.parts[0].text = "Generated text"
        self.node._generate_content = MagicMock(return_value=mock_response)

        self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
            image_file_path="image.png",
        )

        # Check that prep_for_media_conversion was called for the image
        mock_prep_media.assert_called_with("image.png", "image/png")
        # Check that the image part was added to the contents
        self.node._generate_content.assert_called()
        contents = self.node._generate_content.call_args[1]["contents"]
        self.assertIn("image_part", contents)

    def test_generate_content_safety_stop(self):
        """Test generate_content with a safety stop."""
        mock_response = MagicMock()
        mock_response.candidates[0].finish_reason.name = "SAFETY"
        mock_response.candidates[0].safety_ratings = []
        mock_response.candidates[0].content = None
        self.node._generate_content = MagicMock(return_value=mock_response)

        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertIn("Content generation stopped due to safety filters", result[0])

    def test_generate_content_prompt_feedback_block(self):
        """Test generate_content with a prompt feedback block."""
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.prompt_feedback.block_reason = "SAFETY"
        mock_response.prompt_feedback.safety_ratings = []
        self.node._generate_content = MagicMock(return_value=mock_response)

        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertIn("Content blocked due to safety filters on the prompt", result[0])

    def test_generate_content_empty_response(self):
        """Test generate_content with an empty response."""
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.prompt_feedback = None
        self.node._generate_content = MagicMock(return_value=mock_response)

        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertEqual(result, ("No content generated. The response was empty.",))

    def test_generate_content_api_call_error(self):
        """Test generate_content with an API call error."""
        self.node._generate_content = MagicMock(
            side_effect=exceptions.APICallError("API Error")
        )
        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertIn("Error: API Error", result[0])

    def test_generate_content_unexpected_error(self):
        """Test generate_content with an unexpected error."""
        self.node._generate_content = MagicMock(
            side_effect=Exception("Unexpected Error")
        )
        result = self.node.generate_content(
            prompt="a prompt",
            model="GEMINI_PRO",
            temperature=0.7,
            max_output_tokens=8192,
            top_p=1.0,
            top_k=32,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold="BLOCK_MEDIUM_AND_ABOVE",
            hate_speech_threshold="BLOCK_MEDIUM_AND_ABOVE",
            sexually_explicit_threshold="BLOCK_MEDIUM_AND_ABOVE",
            dangerous_content_threshold="BLOCK_MEDIUM_AND_ABOVE",
        )
        self.assertIn("Error: Unexpected Error", result[0])


if __name__ == "__main__":
    unittest.main()
