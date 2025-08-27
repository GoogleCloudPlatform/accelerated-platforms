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
from unittest.mock import MagicMock, patch, ANY, call

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
        # All required fields are present
        self.assertIn("prompt", req)
        self.assertIn("model", req)
        self.assertIn("temperature", req)
        self.assertIn("max_output_tokens", req)
        self.assertIn("top_p", req)
        self.assertIn("top_k", req)
        self.assertIn("candidate_count", req)
        self.assertIn("stop_sequences", req)
        self.assertIn("response_mime_type", req)
        self.assertIn("harassment_threshold", req)
        self.assertIn("hate_speech_threshold", req)
        self.assertIn("sexually_explicit_threshold", req)
        self.assertIn("dangerous_content_threshold", req)

        # All optional fields are present
        self.assertIn("system_instruction", opt)
        self.assertIn("image_file_path", opt)
        self.assertIn("image_mime_type", opt)
        self.assertIn("video_file_path", opt)
        self.assertIn("video_mime_type", opt)
        self.assertIn("audio_file_path", opt)
        self.assertIn("audio_mime_type", opt)
        self.assertIn("gcp_project_id", opt)
        self.assertIn("gcp_region", opt)

        # model list should include default GEMINI_PRO
        model_choices, model_meta = req["model"]
        self.assertTrue(len(model_choices) > 0)
        self.assertEqual(model_meta.get("default"), GeminiModel.GEMINI_PRO.name)

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

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
    def test_init_with_provided_credentials(self, mock_client, mock_meta):
        node = GeminiNode25(gcp_project_id="my-proj", gcp_region="my-region")
        mock_client.assert_called_once_with(
            vertexai=True, project="my-proj", location="my-region", http_options=ANY
        )
        mock_meta.assert_not_called()
        self.assertEqual(node.project_id, "my-proj")
        self.assertEqual(node.region, "my-region")

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
        side_effect=[None, "projects/123/zones/us-central1-a"],
    )
    def test_init_missing_project_raises(self, _mock_meta):
        with self.assertRaisesRegex(ValueError, "GCP Project is required"):
            GeminiNode25()

    @patch(
        "src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata",
        side_effect=["proj-123", None],
    )
    def test_init_missing_region_raises(self, _mock_meta):
        with self.assertRaisesRegex(ValueError, "GCP region is required"):
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


class TestGenerateContentHappyAndOptions(unittest.TestCase):
    def test_stop_sequences_and_response_mime_type_and_system_instruction(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            with patch(
                "src.custom_nodes.google_genmedia.gemini_nodes.types", _FakeTypesModule
            ):
                with patch(
                    "src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion",
                    return_value=None,
                ):
                    node = GeminiNode25.__new__(GeminiNode25)
                    node.client = MagicMock()
                    captured = {}

                    def _fake_generate_content(**kwargs):
                        captured.update(kwargs)
                        fake_part = MagicMock()
                        fake_part.text = "Hi there!"
                        fake_content = MagicMock()
                        fake_content.parts = [fake_part]
                        fake_candidate = MagicMock()
                        fake_candidate.content = fake_content
                        fake_response = MagicMock(candidates=[fake_candidate])
                        fake_response.prompt_feedback = None
                        return fake_response

                    node.client.models.generate_content.side_effect = (
                        _fake_generate_content
                    )

                    result = node.generate_content(
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
                    self.assertEqual(result, ("Hi there!",))
                    self.assertEqual(
                        captured["model"], GeminiModel[GeminiModel.GEMINI_PRO.name]
                    )
                    cfg = captured["config"]
                    self.assertEqual(cfg.temperature, 0.1)
                    self.assertEqual(cfg.max_output_tokens, 42)
                    self.assertEqual(cfg.top_p, 0.9)
                    self.assertEqual(cfg.top_k, 7)
                    self.assertEqual(cfg.candidate_count, 2)
                    self.assertEqual(cfg.response_mime_type, "application/json")
                    self.assertListEqual(cfg.stop_sequences, ["END", "STOP"])
                    self.assertIsNotNone(cfg.system_instruction)
                    self.assertEqual(len(cfg.safety_settings), 4)

    def test_includes_all_media_parts_when_paths_supplied(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            with patch(
                "src.custom_nodes.google_genmedia.gemini_nodes.types", _FakeTypesModule
            ):
                node = GeminiNode25.__new__(GeminiNode25)
                node.client = MagicMock()
                captured = {}

                def _fake_generate_content(**kwargs):
                    captured.update(kwargs)
                    fake_part = MagicMock()
                    fake_part.text = "Hi there!"
                    fake_content = MagicMock()
                    fake_content.parts = [fake_part]
                    fake_candidate = MagicMock()
                    fake_candidate.content = fake_content
                    fake_response = MagicMock(candidates=[fake_candidate])
                    fake_response.prompt_feedback = None
                    return fake_response

                node.client.models.generate_content.side_effect = _fake_generate_content

                with patch(
                    "src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion",
                    side_effect=["IMG", "VID", "AUD"],
                ):
                    _ = node.generate_content(
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
                contents = captured["contents"]
                self.assertEqual(len(contents), 4)
                self.assertIn("IMG", contents)
                self.assertIn("VID", contents)
                self.assertIn("AUD", contents)

    def test_prints_when_media_paths_given_but_no_content(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            with patch(
                "src.custom_nodes.google_genmedia.gemini_nodes.print"
            ) as mock_print:
                with patch(
                    "src.custom_nodes.google_genmedia.gemini_nodes.types",
                    _FakeTypesModule,
                ):
                    with patch(
                        "src.custom_nodes.google_genmedia.gemini_nodes.utils.prep_for_media_conversion",
                        return_value=None,
                    ):
                        node = GeminiNode25.__new__(GeminiNode25)
                        node.client = MagicMock()

                        def _fake_generate_content(**kwargs):
                            pass

                        node.client.models.generate_content.side_effect = (
                            _fake_generate_content
                        )

                        node.generate_content(
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
                        mock_print.assert_has_calls(
                            [
                                call(
                                    "Image path 'a.png' provided but content not retrieved or file not found."
                                ),
                                call(
                                    "Video path 'b.mp4' provided but content not retrieved or file not found."
                                ),
                                call(
                                    "Audio path 'c.mp3' provided but content not retrieved or file not found."
                                ),
                            ]
                        )

    def test_default_response_mime_type(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            with patch(
                "src.custom_nodes.google_genmedia.gemini_nodes.types", _FakeTypesModule
            ):
                node = GeminiNode25.__new__(GeminiNode25)
                node.client = MagicMock()
                captured = {}

                def _fake_generate_content(**kwargs):
                    captured.update(kwargs)

                node.client.models.generate_content.side_effect = _fake_generate_content

                node.generate_content(
                    prompt="hello",
                    model=GeminiModel.GEMINI_PRO.name,
                    temperature=0.1,
                    max_output_tokens=42,
                    top_p=0.9,
                    top_k=7,
                    candidate_count=2,
                    stop_sequences="",
                    response_mime_type="text/plain",
                    harassment_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                    hate_speech_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                    sexually_explicit_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                    dangerous_content_threshold=ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name,
                )
                cfg = captured["config"]
                self.assertEqual(cfg.response_mime_type, "text/plain")


class TestGenerateContentFailures(unittest.TestCase):
    def test_reinit_error_returns_message(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            side_effect=Exception("bad creds"),
        ):
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

    def test_api_call_failure(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            node = GeminiNode25.__new__(GeminiNode25)
            node.client = MagicMock()
            node.client.models.generate_content.side_effect = Exception("API error")
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
            self.assertIn("Error: API error", msg)

    def test_blocked_prompt_feedback(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            node = GeminiNode25.__new__(GeminiNode25)
            node.client = MagicMock()
            mock_response = MagicMock()
            mock_response.candidates = []
            mock_response.prompt_feedback.block_reason = "SAFETY"
            mock_rating = MagicMock()
            mock_rating.category.name = "HATE_SPEECH"
            mock_rating.probability.name = "HIGH"
            mock_response.prompt_feedback.safety_ratings = [mock_rating]
            node.client.models.generate_content.return_value = mock_response

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
            self.assertIn("Content blocked by safety filter: SAFETY", msg)
            self.assertIn("Category: HATE_SPEECH, Probability: HIGH", msg)

    def test_no_candidates_no_feedback(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            node = GeminiNode25.__new__(GeminiNode25)
            node.client = MagicMock()
            mock_response = MagicMock()
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            node.client.models.generate_content.return_value = mock_response

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
            self.assertEqual("No content generated.", msg)

    def test_malformed_response_no_parts(self):
        with patch(
            "src.custom_nodes.google_genmedia.gemini_nodes.GeminiNode25.__init__",
            return_value=None,
        ):
            node = GeminiNode25.__new__(GeminiNode25)
            node.client = MagicMock()
            mock_response = MagicMock()
            mock_candidate = MagicMock()
            mock_candidate.content.parts = []
            mock_response.candidates = [mock_candidate]
            mock_response.prompt_feedback = None
            node.client.models.generate_content.return_value = mock_response

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
            self.assertIn("Error: list index out of range", msg)


if __name__ == "__main__":
    unittest.main()
