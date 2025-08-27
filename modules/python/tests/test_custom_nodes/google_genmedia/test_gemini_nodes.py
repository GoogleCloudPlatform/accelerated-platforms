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

import sys
import unittest
from unittest.mock import MagicMock, patch, ANY

# ComfyUI shim so imports in the module don't explode in test envs
sys.modules.setdefault("folder_paths", MagicMock())

from src.custom_nodes.google_genmedia import gemini_nodes
from src.custom_nodes.google_genmedia import constants

GeminiNode25 = gemini_nodes.GeminiNode25
GeminiModel = constants.GeminiModel
ThresholdOptions = constants.ThresholdOptions


class TestClassAndMappings(unittest.TestCase):
    def test_node_class_and_display_mappings(self):
        self.assertIn("GeminiNode25", gemini_nodes.NODE_CLASS_MAPPINGS)
        self.assertIs(gemini_nodes.NODE_CLASS_MAPPINGS["GeminiNode25"], GeminiNode25)
        self.assertIn("GeminiNode25", gemini_nodes.NODE_DISPLAY_NAME_MAPPINGS)
        self.assertEqual(
            gemini_nodes.NODE_DISPLAY_NAME_MAPPINGS["GeminiNode25"], "Gemini 2.5"
        )

    def test_input_types_shape_and_defaults(self):
        schema = GeminiNode25.INPUT_TYPES()
        self.assertIn("required", schema)
        self.assertIn("optional", schema)
        req = schema["required"]
        opt = schema["optional"]
        # minimal shape checks
        self.assertIn("prompt", req)
        self.assertIn("model", req)
        # model list should include default GEMINI_PRO
        model_choices, model_meta = req["model"]
        self.assertTrue(len(model_choices) > 0)
        self.assertEqual(model_meta.get("default"), GeminiModel.GEMINI_PRO.name)
        # optional GCP overrides exist
        self.assertIn("gcp_project_id", opt)
        self.assertIn("gcp_region", opt)

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
    def test_init_happy_path_metadata(self, mock_client, mock_meta):
        # project id then zone
        mock_meta.side_effect = ["proj-123", "projects/123/zones/us-central1-a"]
        node = GeminiNode25()
        mock_client.assert_called_once_with(
            vertexai=True, project="proj-123", location="us-central1", http_options=ANY
        )
        # sanity on instance vars
        self.assertEqual(node.project_id, "proj-123")
        self.assertEqual(node.region, "us-central1")

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
        side_effect=[None, "projects/123/zones/us-central1-a"],
    )
    def test_init_missing_project_raises(self, _mock_meta):
        with self.assertRaisesRegex(ValueError, "GCP Project is required"):
            GeminiNode25()

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
        return_value="proj-123",
    )
    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.genai.Client",
        side_effect=Exception("kaboom"),
    )
    def test_init_client_failure_raises(self, _mc, _mm):
        with self.assertRaisesRegex(RuntimeError, "Failed to initialize genai.Client"):
            GeminiNode25()


# ---------- Helpers to fake google.genai.types so we can assert internals ----------
class _FakePart:
    @staticmethod
    def from_text(text):
        return {"kind": "text", "text": text}


class _FakeHarmCategory:
    HARM_CATEGORY_HARASSMENT = "HARASSMENT"
    HARM_CATEGORY_HATE_SPEECH = "HATE"
    HARM_CATEGORY_SEXUALLY_EXPLICIT = "SEX"
    HARM_CATEGORY_DANGEROUS_CONTENT = "DANGER"


class _FakeSafetySetting:
    def __init__(self, category, threshold):
        self.category = category
        self.threshold = threshold


class _FakeGenerateContentConfig:
    def __init__(self, temperature, max_output_tokens, top_p, top_k, candidate_count):
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.candidate_count = candidate_count
        self.stop_sequences = []
        self.response_mime_type = "text/plain"
        self.safety_settings = []
        self.system_instruction = None


class _FakeTypesModule:
    Part = _FakePart
    HarmCategory = _FakeHarmCategory
    SafetySetting = _FakeSafetySetting
    GenerateContentConfig = _FakeGenerateContentConfig


# Patch __init__ to NOOP for these generate_content tests so we don't touch real env
@patch(
    "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
    return_value=None,
)
class TestGenerateContentHappyAndOptions(unittest.TestCase):
    def setUp(self):
        self.node = GeminiNode25()
        # fake client + capture of parameters to assert after call
        self.captured = {}
        self.node.client = MagicMock()

        def _fake_generate_content(**kwargs):
            # capture parameters for assertions
            self.captured.update(kwargs)
            fake_part = MagicMock()
            fake_part.text = "Hi there!"
            fake_content = MagicMock()
            fake_content.parts = [fake_part]
            fake_candidate = MagicMock()
            fake_candidate.content = fake_content
            return MagicMock(candidates=[fake_candidate])

        self.node.client.models.generate_content.side_effect = _fake_generate_content

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.types", _FakeTypesModule)
    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion",
        return_value=None,
    )
    def test_stop_sequences_and_response_mime_type_and_system_instruction(
        self, _m_utils, _m_types, _mock_init
    ):
        result = self.node.generate_content(
            prompt="hello",
            model=GeminiModel.GEMINI_PRO.name,
            temperature=0.1,
            max_output_tokens=42,
            top_p=0.9,
            top_k=7,
            candidate_count=2,
            stop_sequences="END,  STOP ",
            response_mime_type="application/json",
            harassment_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            hate_speech_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            sexually_explicit_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            dangerous_content_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            system_instruction="answer briefly",
        )
        # Returned tuple text
        self.assertEqual(result, ("Hi there!",))
        # Model selection was from enum
        self.assertEqual(
            self.captured["model"], GeminiModel[GeminiModel.GEMINI_PRO.name]
        )
        cfg = self.captured["config"]
        self.assertEqual(cfg.temperature, 0.1)
        self.assertEqual(cfg.max_output_tokens, 42)
        self.assertEqual(cfg.top_p, 0.9)
        self.assertEqual(cfg.top_k, 7)
        self.assertEqual(cfg.candidate_count, 2)
        self.assertEqual(cfg.response_mime_type, "application/json")
        self.assertListEqual(cfg.stop_sequences, ["END", "STOP"])
        self.assertIsNotNone(cfg.system_instruction)
        # 4 safety settings should have been set
        self.assertEqual(len(cfg.safety_settings), 4)

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.types", _FakeTypesModule)
    def test_includes_all_media_parts_when_paths_supplied(self, _m_types, _mock_init):
        # Have utils return sentinel parts in sequence
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion",
            side_effect=["IMG", "VID", "AUD"],
        ):
            _ = self.node.generate_content(
                prompt="use media",
                model=GeminiModel.GEMINI_PRO.name,
                temperature=0.1,
                max_output_tokens=5,
                top_p=0.9,
                top_k=1,
                candidate_count=1,
                stop_sequences="",
                response_mime_type="text/plain",
                harassment_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                hate_speech_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                sexually_explicit_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                dangerous_content_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                image_file_path="a.png",
                video_file_path="b.mp4",
                audio_file_path="c.mp3",
            )
        # contents should be prompt + 3 media parts
        contents = self.captured["contents"]
        self.assertEqual(len(contents), 4)
        # the three extra are the sentinel strings we returned
        self.assertIn("IMG", contents)
        self.assertIn("VID", contents)
        self.assertIn("AUD", contents)


class TestGenerateContentReinitFailures(unittest.TestCase):
    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
        side_effect=Exception("bad creds"),
    )
    def test_reinit_error_returns_message(self, _mock_init):
        # Bypass __init__ at construction time
        node = GeminiNode25.__new__(GeminiNode25)
        (msg,) = node.generate_content(
            prompt="x",
            model=GeminiModel.GEMINI_PRO.name,
            temperature=0.0,
            max_output_tokens=1,
            top_p=0.0,
            top_k=1,
            candidate_count=1,
            stop_sequences="",
            response_mime_type="text/plain",
            harassment_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            hate_speech_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            sexually_explicit_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
            dangerous_content_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
        )
        self.assertIn("Error re-initializing Gemini client", msg)


if __name__ == "__main__":
    unittest.main()
