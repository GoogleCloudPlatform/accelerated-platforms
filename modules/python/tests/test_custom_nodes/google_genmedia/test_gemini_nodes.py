# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest
from unittest.mock import MagicMock, patch, ANY

# Mock ComfyUI's folder_paths module before other imports
import sys

sys.modules["folder_paths"] = MagicMock()

from src.custom_nodes.google_genmedia import gemini_nodes
from src.custom_nodes.google_genmedia import constants

GeminiNode25 = gemini_nodes.GeminiNode25
GeminiModel = gemini_nodes.GeminiModel
ThresholdOptions = constants.ThresholdOptions


# --- Test Suite 1: For testing the __init__ method ---
class TestGeminiNodeSetup(unittest.TestCase):
    """
    This class tests ONLY the initialization logic of the GeminiNode25.
    It does NOT mock the __init__ method itself.
    """

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    def test_init_with_metadata_success(self, mock_get_metadata, mock_genai_client):
        """Tests that __init__ works when fetching metadata."""
        mock_get_metadata.side_effect = [
            "test-project",
            "projects/123/zones/us-central1-a",
        ]
        node = GeminiNode25()
        mock_genai_client.assert_called_with(
            vertexai=True,
            project="test-project",
            location="us-central1",
            http_options=ANY,
        )

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    def test_init_missing_project_raises_error(self, mock_get_metadata):
        """Tests that a ValueError is raised if the project ID cannot be found."""
        mock_get_metadata.side_effect = [None, "projects/123/zones/us-central1-a"]
        with self.assertRaisesRegex(ValueError, "GCP Project is required"):
            GeminiNode25()

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
        return_value="fake-project",
    )
    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.genai.Client",
        side_effect=Exception("Auth error"),
    )
    def test_init_client_creation_fails(self, mock_genai_client, mock_get_metadata):
        """Tests that a RuntimeError is raised if the genai.Client fails."""
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize genai.Client"):
            GeminiNode25()


# --- Test Suite 2: For testing the generate_content method ---
@patch(
    "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
    return_value=None,
)
class TestGeminiNodeGenerateContent(unittest.TestCase):
    """
    This class tests ONLY the generate_content logic.
    It completely mocks __init__ to prevent any real setup or API calls.
    """

    # CORRECTED: Removed 'mock_init' from setUp signature, as the class decorator does not pass it here.
    def setUp(self):
        """Set up a fresh node instance for each test."""
        self.node_instance = GeminiNode25()
        self.node_instance.client = MagicMock()
        self.mock_generate_content_api = (
            self.node_instance.client.models.generate_content
        )

    # CORRECTED: Added 'mock_init' to the test method signature, as the class decorator passes it to every test.
    def test_generate_content_success(self, mock_init):
        mock_response = MagicMock(
            candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="Hello!")]))]
        )
        self.mock_generate_content_api.return_value = mock_response
        args = {
            "prompt": "Say hi",
            "model": GeminiModel.GEMINI_PRO.name,
            "temperature": 0.5,
            "max_output_tokens": 100,
            "top_p": 1.0,
            "top_k": 32,
            "candidate_count": 1,
            "stop_sequences": "",
            "response_mime_type": "text/plain",
            "harassment_threshold": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            "hate_speech_threshold": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            "sexually_explicit_threshold": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            "dangerous_content_threshold": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
        }
        result = self.node_instance.generate_content(**args)
        self.assertEqual(result, ("Hello!",))
        self.mock_generate_content_api.assert_called_once()

    def test_generate_content_blocked_by_safety_filter(self, mock_init):
        mock_response = MagicMock(
            candidates=[],
            prompt_feedback=MagicMock(block_reason="SAFETY", safety_ratings=[]),
        )
        self.mock_generate_content_api.return_value = mock_response
        args = {
            "prompt": "bad prompt",
            "model": GeminiModel.GEMINI_PRO.name,
            "temperature": 0.5,
            "max_output_tokens": 100,
            "top_p": 1.0,
            "top_k": 32,
            "candidate_count": 1,
            "stop_sequences": "",
            "response_mime_type": "text/plain",
            "harassment_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "hate_speech_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "sexually_explicit_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "dangerous_content_threshold": "BLOCK_MEDIUM_AND_ABOVE",
        }
        result = self.node_instance.generate_content(**args)
        self.assertIn("Content blocked by safety filter: SAFETY", result[0])

    def test_generate_content_api_call_raises_exception(self, mock_init):
        self.mock_generate_content_api.side_effect = Exception("API limit reached")
        args = {
            "prompt": "a prompt",
            "model": GeminiModel.GEMINI_PRO.name,
            "temperature": 0.5,
            "max_output_tokens": 100,
            "top_p": 1.0,
            "top_k": 32,
            "candidate_count": 1,
            "stop_sequences": "",
            "response_mime_type": "text/plain",
            "harassment_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "hate_speech_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "sexually_explicit_threshold": "BLOCK_MEDIUM_AND_ABOVE",
            "dangerous_content_threshold": "BLOCK_MEDIUM_AND_ABOVE",
        }
        result = self.node_instance.generate_content(**args)
        self.assertIn("Error: API limit reached", result[0])
