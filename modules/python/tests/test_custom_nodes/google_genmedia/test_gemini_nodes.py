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
import pytest
from unittest.mock import MagicMock
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

    # Check prompt
    assert "prompt" in required
    assert required["prompt"] == (
        "STRING",
        {"multiline": True, "default": "Describe the content in detail."},
    )

    # Check model
    assert "model" in required
    expected_models = [model.name for model in GeminiModel]
    assert required["model"][0] == expected_models
    assert required["model"][1] == {"default": GeminiModel.GEMINI_PRO.name}

    # Check a generation config parameter
    assert "temperature" in required
    assert required["temperature"] == (
        "FLOAT",
        {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01},
    )

    # Check a safety setting parameter
    assert "harassment_threshold" in required
    expected_thresholds = [t.name for t in ThresholdOptions]
    assert required["harassment_threshold"][0] == expected_thresholds
    assert required["harassment_threshold"][1] == {
        "default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name
    }

    # --- Check Optional Fields ---
    optional = input_types["optional"]

    # Check system_instruction
    assert "system_instruction" in optional
    assert optional["system_instruction"][0] == "STRING"
    assert "placeholder" in optional["system_instruction"][1]

    # Check a file path
    assert "image_file_path" in optional
    assert optional["image_file_path"][0] == "STRING"
    assert optional["image_file_path"][1]["optional"] is True

    # Check a mime type
    assert "video_mime_type" in optional
    assert isinstance(optional["video_mime_type"][0], list)
    assert optional["video_mime_type"][1]["default"] == "video/mp4"

    # Check a gcp setting
    assert "gcp_project_id" in optional
    assert optional["gcp_project_id"] == (
        "STRING",
        {
            "default": "",
            "tooltip": "GCP project id where Vertex AI API will query Gemini",
        },
    )


def test_generate_content_success(node_instance):
    """Test the generate_content function for a successful API call."""
    # 1. Arrange
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock()]
    mock_response.candidates[0].content.parts[0].text = "Hello from Gemini!"
    node_instance.client.models.generate_content.return_value = mock_response

    # Mock the __init__ method to prevent it from running during the call
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

    # 2. Act
    result = node_instance.generate_content(**args)

    # 3. Assert
    assert result == ("Hello from Gemini!",)
    node_instance.client.models.generate_content.assert_called_once()
    # You can add more specific assertions about the arguments passed to the mock
    call_args, call_kwargs = node_instance.client.models.generate_content.call_args
    assert call_kwargs["model"].name == GeminiModel.GEMINI_PRO.name
    assert call_kwargs["config"].temperature == 0.5
