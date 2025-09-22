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

"""Unit tests for veo3_api.py"""
import unittest
from unittest.mock import Mock, patch

from src.custom_nodes.google_genmedia.exceptions import ConfigurationError
from src.custom_nodes.google_genmedia.veo3_api import Veo3API


class TestVeo3API(unittest.TestCase):
    """Test cases for Veo3API class."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region = "us-central1"
        with patch(
            "src.custom_nodes.google_genmedia.base_api.GoogleGenAIBaseAPI.__init__",
            return_value=None,
        ):
            self.api = Veo3API(project_id=self.project_id, region=self.region)
            self.api.client = Mock()

    @patch("src.custom_nodes.google_genmedia.utils.generate_video_from_text")
    def test_generate_video_from_text_success(self, mock_generate_video):
        """Test successful video generation from text."""
        self.api.generate_video_from_text(
            model="VEO_3_PREVIEW",
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=8,
            generate_audio=True,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="gs://bucket/path",
            output_resolution="720p",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_text_empty_prompt(self):
        """Test that an empty prompt raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                model="VEO_3_PREVIEW",
                prompt="",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_duration(self):
        """Test that an invalid duration raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                model="VEO_3_PREVIEW",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=10,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_sample_count(self):
        """Test that an invalid sample count raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                model="VEO_3_PREVIEW",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=5,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_aspect_ratio(self):
        """Test that an invalid aspect ratio raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                model="VEO_3_PREVIEW",
                prompt="a cat",
                aspect_ratio="1:1",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_resolution(self):
        """Test that an invalid resolution raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                model="VEO_3_PREVIEW",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="480p",
                negative_prompt="",
                seed=123,
            )

    @patch("src.custom_nodes.google_genmedia.utils.generate_video_from_image")
    def test_generate_video_from_image_success(self, mock_generate_video):
        """Test successful video generation from image."""
        self.api.generate_video_from_image(
            model="VEO_3_PREVIEW",
            image=Mock(),
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=8,
            generate_audio=True,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="gs://bucket/path",
            output_resolution="720p",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_image_invalid_duration(self):
        """Test that an invalid duration raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                model="VEO_3_PREVIEW",
                image=Mock(),
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=10,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_image_invalid_sample_count(self):
        """Test that an invalid sample count raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                model="VEO_3_PREVIEW",
                image=Mock(),
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=5,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_image_no_image(self):
        """Test that no image raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                model="VEO_3_PREVIEW",
                image=None,
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_image_invalid_aspect_ratio(self):
        """Test that an invalid aspect ratio raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                model="VEO_3_PREVIEW",
                image=Mock(),
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="1:1",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_image_invalid_resolution(self):
        """Test that an invalid resolution raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                model="VEO_3_PREVIEW",
                image=Mock(),
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="480p",
                negative_prompt="",
                seed=123,
            )

    @patch(
        "src.custom_nodes.google_genmedia.utils.validate_gcs_uri_and_image",
        return_value=(True, ""),
    )
    @patch("src.custom_nodes.google_genmedia.utils.generate_video_from_gcsuri_image")
    def test_generate_video_from_gcsuri_image_success(
        self, mock_generate_video, mock_validate_gcs
    ):
        """Test successful video generation from GCS image."""
        self.api.generate_video_from_gcsuri_image(
            model="VEO_3_PREVIEW",
            gcsuri="gs://bucket/path",
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=8,
            generate_audio=True,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="gs://bucket/path",
            output_resolution="720p",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_gcsuri_image_no_gcsuri(self):
        """Test that no GCS URI raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri=None,
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_image_invalid_duration(self):
        """Test that an invalid duration raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://bucket/path",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=10,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_image_invalid_sample_count(self):
        """Test that an invalid sample count raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://bucket/path",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=5,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_image_invalid_aspect_ratio(self):
        """Test that an invalid aspect ratio raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://bucket/path",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="1:1",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_image_invalid_resolution(self):
        """Test that an invalid resolution raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://bucket/path",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="480p",
                negative_prompt="",
                seed=123,
            )

    @patch(
        "src.custom_nodes.google_genmedia.utils.validate_gcs_uri_and_image",
        return_value=(False, "Invalid GCS URI"),
    )
    def test_generate_video_from_gcsuri_image_invalid_gcs_uri(self, mock_validate_gcs):
        """Test that an invalid GCS URI raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://invalid",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_gcsuri_image_unsupported_format(self):
        """Test that an unsupported image format raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                model="VEO_3_PREVIEW",
                gcsuri="gs://bucket/path",
                image_format="GIF",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=8,
                generate_audio=True,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                output_resolution="720p",
                negative_prompt="",
                seed=123,
            )


if __name__ == "__main__":
    unittest.main()
