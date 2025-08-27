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
from src.custom_nodes.google_genmedia.veo2_nodes import (
    Veo2TextToVideoNode,
    Veo2ImageToVideoNode,
    Veo2GcsUriImageToVideoNode,
)


class TestVeo2Nodes(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_text_to_video_node(self, mock_veo_api):
        # Arrange
        node = Veo2TextToVideoNode()
        mock_api_instance = MagicMock()
        mock_api_instance.generate_video_from_text.return_value = ["/fake/video.mp4"]
        mock_veo_api.return_value = mock_api_instance

        # Act
        (result,) = node.generate(prompt="test")

        # Assert
        self.assertEqual(result, ["/fake/video.mp4"])
        mock_api_instance.generate_video_from_text.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_image_to_video_node(self, mock_veo_api):
        # Arrange
        node = Veo2ImageToVideoNode()
        mock_api_instance = MagicMock()
        mock_api_instance.generate_video_from_image.return_value = ["/fake/video.mp4"]
        mock_veo_api.return_value = mock_api_instance
        image_tensor = torch.rand(1, 256, 256, 3)

        # Act
        (result,) = node.generate(image=image_tensor, prompt="test")

        # Assert
        self.assertEqual(result, ["/fake/video.mp4"])
        mock_api_instance.generate_video_from_image.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_gcsuri_image_to_video_node(self, mock_veo_api):
        # Arrange
        node = Veo2GcsUriImageToVideoNode()
        mock_api_instance = MagicMock()
        mock_api_instance.generate_video_from_gcsuri_image.return_value = [
            "/fake/video.mp4"
        ]
        mock_veo_api.return_value = mock_api_instance

        # Act
        (result,) = node.generate(gcsuri="gs://bucket/img.png", prompt="test")

        # Assert
        self.assertEqual(result, ["/fake/video.mp4"])
        mock_api_instance.generate_video_from_gcsuri_image.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.veo2_nodes.Veo2API")
    def test_init_failure(self, mock_veo_api):
        # Arrange
        mock_veo_api.side_effect = Exception("Init failed")

        # Act & Assert
        with self.assertRaisesRegex(
            RuntimeError, "Failed to initialize Veo API: Init failed"
        ):
            Veo2TextToVideoNode().generate(prompt="test")


if __name__ == "__main__":
    unittest.main()
