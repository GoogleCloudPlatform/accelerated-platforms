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
from unittest.mock import patch, MagicMock
import torch
import sys

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.veo3_api import Veo3API, Veo3Model


class TestVeo3API(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.veo3_api.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.veo3_api.genai.Client")
    def setUp(self, mock_genai_client, mock_get_gcp_metadata):
        mock_get_gcp_metadata.side_effect = ["test-project", "us-central1"]
        self.mock_client = MagicMock()
        mock_genai_client.return_value = self.mock_client
        self.api = Veo3API(project_id="test-project", region="us-central1")

    @patch("src.custom_nodes.google_genmedia.veo3_api.utils.generate_video_from_text")
    def test_generate_video_from_text_success(self, mock_generate):
        mock_generate.return_value = ["/path/to/video.mp4"]

        paths = self.api.generate_video_from_text(
            model=Veo3Model.VEO_3_PREVIEW.name,
            prompt="a test video",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            generate_audio=True,
            enhance_prompt=True,
            sample_count=1,
            output_gcs_uri="",
            output_resolution="720p",
            negative_prompt="",
            seed=123,
        )

        self.assertEqual(paths, ["/path/to/video.mp4"])
        mock_generate.assert_called_once()

    def test_generate_video_from_text_invalid_duration(self):
        with self.assertRaises(ValueError):
            self.api.generate_video_from_text(
                model=Veo3Model.VEO_3_PREVIEW.name,
                prompt="a test video",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow_adult",
                duration_seconds=5,  # Invalid
                generate_audio=True,
                enhance_prompt=True,
                sample_count=1,
                output_gcs_uri="",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_init_raises_error_if_project_not_found(self):
        """Tests __init__ raises ValueError if get_gcp_metadata returns None for project."""
        # This requires re-patching because setUp has its own patches
        with patch(
            "src.custom_nodes.google_genmedia.veo3_api.get_gcp_metadata",
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "GCP Project is required"):
                Veo3API(project_id=None, region="us-central1")

    # --- Additional tests for generate_video_from_text validation ---

    def test_generate_video_from_text_invalid_sample_count(self):
        """Tests ValueError for sample_count outside the valid range [1, 2]."""
        with self.assertRaisesRegex(ValueError, "sample_count must be between 1 and 2"):
            self.api.generate_video_from_text(
                model=Veo3Model.VEO_3_PREVIEW.name,
                prompt="a test",
                duration_seconds=8,
                aspect_ratio="16:9",
                output_resolution="720p",
                sample_count=3,  # Invalid
                compression_quality="optimized",
                person_generation="allow_adult",
                generate_audio=True,
                enhance_prompt=True,
                output_gcs_uri="",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_aspect_ratio(self):
        """Tests ValueError for incorrect aspect ratio."""
        with self.assertRaisesRegex(
            ValueError, "can only generate videos of aspect ratio 16:9"
        ):
            self.api.generate_video_from_text(
                model=Veo3Model.VEO_3_PREVIEW.name,
                prompt="a test",
                duration_seconds=8,
                aspect_ratio="1:1",  # Invalid
                output_resolution="720p",
                sample_count=1,
                compression_quality="optimized",
                person_generation="allow_adult",
                generate_audio=True,
                enhance_prompt=True,
                output_gcs_uri="",
                negative_prompt="",
                seed=123,
            )

    # --- Tests for generate_video_from_image ---

    @patch("src.custom_nodes.google_genmedia.veo3_api.utils.generate_video_from_image")
    def test_generate_video_from_image_success(self, mock_generate):
        """Tests the success path for generating a video from an image tensor."""
        mock_generate.return_value = ["/path/to/generated_video.mp4"]
        fake_image_tensor = torch.rand(1, 128, 128, 3)

        paths = self.api.generate_video_from_image(
            model=Veo3Model.VEO_3_PREVIEW.name,
            image=fake_image_tensor,
            image_format="PNG",
            prompt="animate this",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="",
            output_resolution="720p",
            negative_prompt="",
            seed=456,
        )

        self.assertEqual(paths, ["/path/to/generated_video.mp4"])
        mock_generate.assert_called_once()

    def test_generate_video_from_image_none_image(self):
        """Tests that a ValueError is raised if the image tensor is None."""
        with self.assertRaisesRegex(ValueError, "Image input .* cannot be None"):
            self.api.generate_video_from_image(
                model=Veo3Model.VEO_3_PREVIEW.name,
                image=None,  # Invalid
                image_format="PNG",
                prompt="a prompt",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow_adult",
                duration_seconds=8,
                generate_audio=False,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="",
                output_resolution="720p",
                negative_prompt="",
                seed=456,
            )

    # --- Tests for generate_video_from_gcsuri_image ---

    @patch(
        "src.custom_nodes.google_genmedia.veo3_api.utils.generate_video_from_gcsuri_image"
    )
    @patch(
        "src.custom_nodes.google_genmedia.veo3_api.utils.validate_gcs_uri_and_image",
        return_value=(True, "Valid URI"),
    )
    def test_generate_video_from_gcsuri_image_success(
        self, mock_validate, mock_generate
    ):
        """Tests the success path for generating video from a GCS URI."""
        mock_generate.return_value = ["/path/to/gcs_video.mp4"]
        gcs_uri = "gs://my-bucket/image.png"

        paths = self.api.generate_video_from_gcsuri_image(
            model=Veo3Model.VEO_3_PREVIEW.name,
            gcsuri=gcs_uri,
            image_format="PNG",
            prompt="animate this gcs image",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="",
            output_resolution="720p",
            negative_prompt="",
            seed=789,
        )

        self.assertEqual(paths, ["/path/to/gcs_video.mp4"])
        mock_validate.assert_called_once_with(gcs_uri)
        mock_generate.assert_called_once()

    @patch(
        "src.custom_nodes.google_genmedia.veo3_api.utils.validate_gcs_uri_and_image",
        return_value=(False, "Invalid URI"),
    )
    def test_generate_video_from_gcsuri_image_invalid_uri(self, mock_validate):
        """Tests that a ValueError is raised if the GCS URI validation fails."""
        with self.assertRaisesRegex(ValueError, "Invalid URI"):
            self.api.generate_video_from_gcsuri_image(
                model=Veo3Model.VEO_3_PREVIEW.name,
                gcsuri="gs://bad-uri",
                image_format="PNG",
                prompt="a prompt",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow_adult",
                duration_seconds=8,
                generate_audio=False,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="",
                output_resolution="720p",
                negative_prompt="",
                seed=789,
            )

    # --- NEWLY ADDED VALIDATION TESTS ---

    def test_generate_video_from_text_empty_prompt(self):
        """Tests ValueError for an empty text prompt."""
        with self.assertRaisesRegex(ValueError, "Prompt cannot be empty"):
            self.api.generate_video_from_text(
                model=Veo3Model.VEO_3_PREVIEW.name,
                prompt=" ",
                duration_seconds=8,
                aspect_ratio="16:9",
                output_resolution="720p",
                sample_count=1,
                compression_quality="optimized",
                person_generation="allow_adult",
                generate_audio=True,
                enhance_prompt=True,
                output_gcs_uri="",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_unsupported_format(self):
        """Tests ValueError for an unsupported image format in the GCS method."""
        with patch(
            "src.custom_nodes.google_genmedia.veo3_api.utils.validate_gcs_uri_and_image",
            return_value=(True, "Valid"),
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported image format: GIF"):
                self.api.generate_video_from_gcsuri_image(
                    model=Veo3Model.VEO_3_PREVIEW.name,
                    gcsuri="gs://a/b.gif",
                    image_format="GIF",  # Invalid
                    prompt="a prompt",
                    aspect_ratio="16:9",
                    compression_quality="optimized",
                    person_generation="allow_adult",
                    duration_seconds=8,
                    generate_audio=False,
                    enhance_prompt=False,
                    sample_count=1,
                    output_gcs_uri="",
                    output_resolution="720p",
                    negative_prompt="",
                    seed=789,
                )

    @patch("src.custom_nodes.google_genmedia.veo3_api.utils.generate_video_from_text")
    def test_generate_video_from_text_api_failure(self, mock_generate):
        mock_generate.side_effect = RuntimeError("API Error")

        with self.assertRaises(RuntimeError):
            self.api.generate_video_from_text(
                model=Veo3Model.VEO_3_PREVIEW.name,
                prompt="a test video",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow_adult",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=True,
                sample_count=1,
                output_gcs_uri="",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )


if __name__ == "__main__":
    unittest.main()
