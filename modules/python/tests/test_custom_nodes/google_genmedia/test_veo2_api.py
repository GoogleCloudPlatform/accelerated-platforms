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

import unittest
from unittest.mock import patch, MagicMock
import torch
import sys
from unittest.mock import MagicMock

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.veo2_api import Veo2API


class TestVeo2API(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.veo2_api.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.veo2_api.genai.Client")
    def setUp(self, mock_genai_client, mock_get_gcp_metadata):
        mock_get_gcp_metadata.side_effect = ["test-project", "us-central1"]
        self.mock_client = MagicMock()
        mock_genai_client.return_value = self.mock_client
        self.api = Veo2API(project_id="test-project", region="us-central1")

    @patch("src.custom_nodes.google_genmedia.veo2_api.utils.generate_video_from_text")
    def test_generate_video_from_text_success(self, mock_generate):
        mock_generate.return_value = ["/path/to/video.mp4"]

        paths = self.api.generate_video_from_text(
            prompt="a test video",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            enhance_prompt=True,
            sample_count=1,
            output_gcs_uri="",
            negative_prompt="",
            seed=123,
        )

        self.assertEqual(paths, ["/path/to/video.mp4"])
        mock_generate.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.veo2_api.utils.generate_video_from_image")
    def test_generate_video_from_image_success(self, mock_generate):
        mock_generate.return_value = ["/path/to/video.mp4"]
        image_tensor = torch.rand(1, 256, 256, 3)

        paths = self.api.generate_video_from_image(
            image=image_tensor,
            image_format="PNG",
            prompt="a test video",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            enhance_prompt=True,
            sample_count=1,
            last_frame=None,
            output_gcs_uri="",
            negative_prompt="",
            seed=123,
        )

        self.assertEqual(paths, ["/path/to/video.mp4"])
        mock_generate.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    @patch(
        "src.custom_nodes.google_genmedia.veo2_api.utils.generate_video_from_gcsuri_image"
    )
    def test_generate_video_from_gcsuri_image_success(
        self, mock_generate, mock_storage_client
    ):
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.content_type = "image/png"
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_generate.return_value = ["/path/to/video.mp4"]

        paths = self.api.generate_video_from_gcsuri_image(
            gcsuri="gs://bucket/image.png",
            image_format="PNG",
            prompt="a test video",
            aspect_ratio="16:9",
            compression_quality="optimized",
            person_generation="allow_adult",
            duration_seconds=8,
            enhance_prompt=True,
            sample_count=1,
            last_frame_gcsuri="",
            output_gcs_uri="",
            negative_prompt="",
            seed=123,
        )

        self.assertEqual(paths, ["/path/to/video.mp4"])
        mock_generate.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.veo2_api.utils.generate_video_from_text")
    def test_generate_video_from_text_api_failure(self, mock_generate):
        mock_generate.side_effect = RuntimeError("API Error")

        with self.assertRaises(RuntimeError):
            self.api.generate_video_from_text(
                prompt="a test video",
                aspect_ratio="16:9",
                compression_quality="optimized",
                person_generation="allow_adult",
                duration_seconds=8,
                enhance_prompt=True,
                sample_count=1,
                output_gcs_uri="",
                negative_prompt="",
                seed=123,
            )


if __name__ == "__main__":
    unittest.main()
