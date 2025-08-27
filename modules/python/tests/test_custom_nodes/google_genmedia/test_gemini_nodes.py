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
import pytest
from unittest.mock import MagicMock, patch, ANY
import unittest
import sys

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia import gemini_nodes
from src.custom_nodes.google_genmedia import constants

GeminiNode25 = gemini_nodes.GeminiNode25
GeminiModel = gemini_nodes.GeminiModel
ThresholdOptions = constants.ThresholdOptions


@pytest.fixture
def node_instance(monkeypatch):
    """Fixture to create a GeminiNode25 node instance."""
    # Use monkeypatch to prevent the real __init__ from running during setup.
    # This stops it from making actual GCP calls.
    monkeypatch.setattr(GeminiNode25, "__init__", lambda *args, **kwargs: None)

    # Now that __init__ is neutralized, we can safely create an instance
    # and attach our mock client to it for testing.
    instance = GeminiNode25()
    instance.client = MagicMock()
    return instance


def node_model():
    """Fixture to create an Example node instance."""
    return GeminiModel()


def test_node_initilization(node_instance):
    """Test that the node can be instantiated."""
    assert isinstance(node_instance, GeminiNode25)


def test_return_types(node_instance):
    """Test the node's metadata."""
    assert node_instance.CATEGORY == ("Google AI/Gemini")
    assert node_instance.FUNCTION == ("generate_content")
    assert node_instance.RETURN_TYPES == ("STRING",)
    assert node_instance.RETURN_NAMES == ("generated_output",)


def test_input_types_structure():
    """Test the structure and keys of the INPUT_TYPES class method."""
    input_types = GeminiNode25.INPUT_TYPES()
    assert isinstance(input_types, dict)
    assert "required" in input_types
    assert "optional" in input_types
    assert isinstance(input_types["required"], dict)
    assert isinstance(input_types["optional"], dict)


def test_input_types_content():
    """Test the specific content and values within INPUT_TYPES."""
    input_types = GeminiNode25.INPUT_TYPES()

    # --- Check Required Fields ---
    required = input_types["required"]
    assert "prompt" in required
    assert required["prompt"] == (
        "STRING",
        {"multiline": True, "default": "Describe the content in detail."},
    )
    assert "model" in required
    expected_models = [model.name for model in GeminiModel]
    assert required["model"][0] == expected_models
    assert required["model"][1] == {"default": GeminiModel.GEMINI_PRO.name}

    # --- Check Optional Fields ---
    optional = input_types["optional"]
    assert "system_instruction" in optional
    assert optional["system_instruction"][0] == "STRING"


def test_generate_content_success(node_instance):
    """Test the generate_content function for a successful API call."""
    # Arrange
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock()]
    mock_response.candidates[0].content.parts[0].text = "Hello from Gemini!"
    node_instance.client.models.generate_content.return_value = mock_response
    node_instance.__init__ = MagicMock()

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

    # Act
    result = node_instance.generate_content(**args)

    # Assert
    assert result == ("Hello from Gemini!",)
    node_instance.client.models.generate_content.assert_called_once()
    call_args, call_kwargs = node_instance.client.models.generate_content.call_args
    assert call_kwargs["model"].name == GeminiModel.GEMINI_PRO.name
    assert call_kwargs["config"].temperature == 0.5


# =================================================================================
# --- NEW TESTS ADDED FOR INCREASED COVERAGE ---
# =================================================================================

# --- Tests for the __init__ method ---


@patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
@patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
def test_init_with_metadata_success(mock_get_metadata, mock_genai_client):
    """Tests that __init__ works when fetching metadata."""
    mock_get_metadata.side_effect = ["fake-project", "projects/123/zones/us-central1-a"]
    node = GeminiNode25()
    mock_genai_client.assert_called_with(
        vertexai=True, project="fake-project", location="us-central1", http_options=ANY
    )


@patch(
    "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata", return_value=None
)
@patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
def test_init_missing_project_raises_error(self,mock_get_metadata):
    """Tests that a ValueError is raised if the project ID cannot be found."""
    # UPDATED LINE: Use side_effect to return different values for each call
    mock_get_metadata.side_effect = [None, "projects/123/zones/us-central1-a"]

    # Act & Assert: Expect a ValueError
    with pytest.raises(ValueError, match="GCP Project is required"):
        GeminiNode25()


@patch(
    "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
    return_value="fake-project",
)
@patch(
    "src.custom_nodes.google_genmedia.gemini_nodes.genai.Client",
    side_effect=Exception("Auth error"),
)
def test_init_client_creation_fails(mock_genai_client, mock_get_metadata):
    """Tests that a RuntimeError is raised if the genai.Client fails."""
    with pytest.raises(RuntimeError, match="Failed to initialize genai.Client"):
        GeminiNode25()


# --- Tests for the generate_content method ---


def test_generate_content_blocked_by_safety_filter(node_instance):
    """Tests the response format when content is blocked."""
    mock_response = MagicMock()
    mock_response.candidates = []
    mock_response.prompt_feedback.block_reason = "SAFETY"
    mock_response.prompt_feedback.safety_ratings = []
    node_instance.client.models.generate_content.return_value = mock_response
    node_instance.__init__ = MagicMock()

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

    result = node_instance.generate_content(**args)
    assert "Content blocked by safety filter: SAFETY" in result[0]


def test_generate_content_api_call_raises_exception(node_instance):
    """Tests that the function handles exceptions from the API call."""
    node_instance.client.models.generate_content.side_effect = Exception(
        "API limit reached"
    )
    node_instance.__init__ = MagicMock()
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

    result = node_instance.generate_content(**args)
    assert "Error: API limit reached" in result[0]


@patch("src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion")
def test_generate_content_with_image(mock_prep_media, node_instance):
    """Tests that media files are correctly processed and included."""
    mock_prep_media.return_value = "fake_image_part"
    mock_response = MagicMock()
    mock_response.candidates = [
        MagicMock(content=MagicMock(parts=[MagicMock(text="Image description")]))
    ]
    node_instance.client.models.generate_content.return_value = mock_response
    node_instance.__init__ = MagicMock()

    args = {
        "prompt": "describe this image",
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
        "image_file_path": "/fake/path/to/image.png",
    }

    node_instance.generate_content(**args)
    mock_prep_media.assert_called_with("/fake/path/to/image.png", "image/png")
    call_args, call_kwargs = node_instance.client.models.generate_content.call_args
    assert len(call_kwargs["contents"]) == 2
    assert call_kwargs["contents"][1] == "fake_image_part"
