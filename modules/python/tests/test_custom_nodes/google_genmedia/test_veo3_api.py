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


if __name__ == "__main__":
    unittest.main()
