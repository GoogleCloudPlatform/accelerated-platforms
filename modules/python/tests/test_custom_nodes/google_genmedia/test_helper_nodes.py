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
from unittest.mock import patch, MagicMock, mock_open
import torch
import numpy as np
import sys
from unittest.mock import MagicMock

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.helper_nodes import (
    VeoVideoToVHSNode,
    VeoVideoSaveAndPreview,
)


class TestVeoVideoToVHSNode(unittest.TestCase):
    def setUp(self):
        self.node = VeoVideoToVHSNode()

    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.os.path.exists",
        return_value=True,
    )
    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.os.path.isfile",
        return_value=True,
    )
    @patch("src.custom_nodes.google_genmedia.helper_nodes.cv2.VideoCapture")
    def test_convert_videos_success(self, mock_video_capture, mock_isfile, mock_exists):
        # Arrange
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = [
            240,
            1920,
            1080,
        ]  # total_frames, width, height
        mock_cap_instance.read.return_value = (
            True,
            np.zeros((1080, 1920, 3), dtype=np.uint8),
        )
        mock_video_capture.return_value = mock_cap_instance

        video_paths = ["/fake/video1.mp4"]

        # Act
        result = self.node.convert_videos(video_paths)

        # Assert
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], torch.Tensor)
        self.assertEqual(result[0].shape[0], 120)  # no_of_frames
        self.assertEqual(result[0].shape[1], 1080)
        self.assertEqual(result[0].shape[2], 1920)
        self.assertEqual(result[0].shape[3], 3)
        mock_video_capture.assert_called_with("/fake/video1.mp4")
        self.assertEqual(mock_cap_instance.set.call_count, 120)

    def test_convert_videos_no_paths(self):
        # Act
        result = self.node.convert_videos([])
        # Assert
        self.assertEqual(result[0].shape, (1, 512, 512, 3))

    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.os.path.exists",
        return_value=False,
    )
    def test_convert_videos_file_not_exist(self, mock_exists):
        result = self.node.convert_videos(["/fake/video.mp4"])
        self.assertEqual(result[0].shape, (1, 512, 512, 3))


class TestVeoVideoSaveAndPreview(unittest.TestCase):
    def setUp(self):
        self.node = VeoVideoSaveAndPreview()

    @patch("src.custom_nodes.google_genmedia.helper_nodes.os.makedirs")
    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.os.path.exists",
        return_value=True,
    )
    @patch("src.custom_nodes.google_genmedia.helper_nodes.os.path.abspath", lambda x: x)
    @patch("src.custom_nodes.google_genmedia.helper_nodes.shutil.copy2")
    @patch("src.custom_nodes.google_genmedia.helper_nodes.VideoFileClip")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fakedata")
    @patch("src.custom_nodes.google_genmedia.helper_nodes.hashlib.md5")
    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.folder_paths.get_temp_directory",
        return_value="/tmp/fake_temp_dir",
    )
    def test_preview_video_save(
        self,
        mock_get_temp_directory,
        mock_md5,
        mock_open_file,
        mock_videofileclip,
        mock_copy,
        mock_exists,
        mock_makedirs,
    ):
        # Arrange
        mock_clip_instance = MagicMock()
        mock_clip_instance.duration = 5.0
        mock_clip_instance.size = (1920, 1080)
        mock_videofileclip.return_value.__enter__.return_value = mock_clip_instance
        mock_md5.return_value.hexdigest.return_value = "12345678"

        video_paths = ["/fake/video.mp4"]
        # Act
        result = self.node.preview_video(
            video_paths, True, True, False, True, "test_prefix"
        )

        # Assert
        self.assertIn("ui", result)
        self.assertIn("video", result["ui"])
        self.assertEqual(len(result["ui"]["video"]), 1)
        video_info = result["ui"]["video"][0]
        self.assertTrue(video_info["filename"].startswith("test_prefix_"))
        self.assertEqual(video_info["subfolder"], "veo")
        self.assertEqual(video_info["type"], "output")
        mock_copy.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.helper_nodes.os.makedirs")
    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.os.path.exists",
        return_value=True,
    )
    @patch("src.custom_nodes.google_genmedia.helper_nodes.os.path.abspath", lambda x: x)
    @patch("src.custom_nodes.google_genmedia.helper_nodes.shutil.copy2")
    @patch("src.custom_nodes.google_genmedia.helper_nodes.VideoFileClip")
    @patch(
        "src.custom_nodes.google_genmedia.helper_nodes.folder_paths.get_temp_directory",
        return_value="/tmp/fake_temp_dir",
    )
    def test_preview_video_preview_only(
        self,
        mock_get_temp_directory,
        mock_videofileclip,
        mock_copy,
        mock_exists,
        mock_makedirs,
    ):
        # Arrange
        mock_clip_instance = MagicMock()
        mock_clip_instance.duration = 5.0
        mock_clip_instance.size = (1920, 1080)
        mock_videofileclip.return_value.__enter__.return_value = mock_clip_instance

        video_paths = ["/tmp/video.mp4"]
        # Act
        result = self.node.preview_video(
            video_paths, True, True, False, False, "test_prefix"
        )

        # Assert
        self.assertIn("ui", result)
        self.assertIn("video", result["ui"])
        self.assertEqual(len(result["ui"]["video"]), 1)
        video_info = result["ui"]["video"][0]
        self.assertEqual(video_info["filename"], "video.mp4")
        self.assertEqual(video_info["subfolder"], "temp")
        self.assertEqual(video_info["type"], "temp")
        mock_copy.assert_called_once_with(
            "/tmp/video.mp4", "/tmp/fake_temp_dir/video.mp4"
        )


if __name__ == "__main__":
    unittest.main()
