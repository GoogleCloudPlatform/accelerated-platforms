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

"""Unit tests for veo2_api.py"""
import unittest
from unittest.mock import Mock, patch

from src.custom_nodes.google_genmedia.exceptions import ConfigurationError
from src.custom_nodes.google_genmedia.veo2_api import Veo2API


class TestVeo2API(unittest.TestCase):
    """Test cases for Veo2API class."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region = "us-central1"
        with patch(
            "src.custom_nodes.google_genmedia.base_api.GoogleGenAIBaseAPI.__init__",
            return_value=None,
        ):
            self.api = Veo2API(project_id=self.project_id, region=self.region)
            self.api.client = Mock()

    @patch("src.custom_nodes.google_genmedia.utils.generate_video_from_text")
    def test_generate_video_from_text_success(self, mock_generate_video):
        """Test successful video generation from text."""
        self.api.generate_video_from_text(
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri="gs://bucket/path",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_text_empty_prompt(self):
        """Test that an empty prompt raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                prompt="",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=5,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_duration(self):
        """Test that an invalid duration raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=10,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri="gs://bucket/path",
                negative_prompt="",
                seed=123,
            )

    def test_generate_video_from_text_invalid_sample_count(self):
        """Test that an invalid sample count raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_text(
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=5,
                enhance_prompt=False,
                sample_count=5,
                output_gcs_uri="gs://bucket/path",
                negative_prompt="",
                seed=123,
            )

    @patch("src.custom_nodes.google_genmedia.utils.generate_video_from_image")
    def test_generate_video_from_image_success(self, mock_generate_video):
        """Test successful video generation from image."""
        self.api.generate_video_from_image(
            image=Mock(),
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            enhance_prompt=False,
            sample_count=1,
            last_frame=None,
            output_gcs_uri="gs://bucket/path",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_image_no_image(self):
        """Test that no image raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_image(
                image=None,
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=5,
                enhance_prompt=False,
                sample_count=1,
                last_frame=None,
                output_gcs_uri="gs://bucket/path",
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
            gcsuri="gs://bucket/path",
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            enhance_prompt=False,
            sample_count=1,
            last_frame_gcsuri=None,
            output_gcs_uri="gs://bucket/path",
            negative_prompt="",
            seed=123,
        )
        mock_generate_video.assert_called_once()

    def test_generate_video_from_gcsuri_image_no_gcsuri(self):
        """Test that no GCS URI raises a ConfigurationError."""
        with self.assertRaises(ConfigurationError):
            self.api.generate_video_from_gcsuri_image(
                gcsuri=None,
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=5,
                enhance_prompt=False,
                sample_count=1,
                last_frame_gcsuri=None,
                output_gcs_uri="gs://bucket/path",
                negative_prompt="",
                seed=123,
            )


if __name__ == "__main__":
    unittest.main()
