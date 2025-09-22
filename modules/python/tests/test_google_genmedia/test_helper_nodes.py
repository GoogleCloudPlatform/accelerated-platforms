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

"""Unit tests for helper_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import torch
import numpy as np

from src.custom_nodes.google_genmedia.helper_nodes import (
    VeoVideoToVHSNode,
    VeoVideoSaveAndPreview,
)


class TestHelperNodes(unittest.TestCase):
    """Test cases for helper nodes."""

    def test_veo_video_to_vhs_initialization(self):
        """Test that the VeoVideoToVHSNode can be initialized."""
        node = VeoVideoToVHSNode()
        self.assertIsNotNone(node)

    def test_veo_video_save_and_preview_initialization(self):
        """Test that the VeoVideoSaveAndPreview can be initialized."""
        node = VeoVideoSaveAndPreview()
        self.assertIsNotNone(node)

    def test_convert_videos_no_paths(self):
        """Test convert_videos with no video paths."""
        node = VeoVideoToVHSNode()
        result = node.convert_videos([])
        self.assertEqual(result[0].shape, (1, 512, 512, 3))

    @patch("os.path.exists", return_value=False)
    def test_convert_videos_non_existent_path(self, mock_exists):
        """Test convert_videos with a non-existent video path."""
        node = VeoVideoToVHSNode()
        result = node.convert_videos(["non_existent.mp4"])
        # It should return a dummy image
        self.assertEqual(result[0].shape, (1, 512, 512, 3))


    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=False)
    def test_convert_videos_not_a_file(self, mock_isfile, mock_exists):
        """Test convert_videos with a path that is not a file."""
        node = VeoVideoToVHSNode()
        result = node.convert_videos(["not_a_file"])
        self.assertEqual(result[0].shape, (1, 512, 512, 3))

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("cv2.VideoCapture")
    def test_convert_videos_cannot_open(self, mock_videocapture, mock_isfile, mock_exists):
        """Test convert_videos with a video that cannot be opened."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_videocapture.return_value = mock_cap
        node = VeoVideoToVHSNode()
        result = node.convert_videos(["cannot_open.mp4"])
        self.assertEqual(result[0].shape, (1, 512, 512, 3))

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("cv2.VideoCapture")
    def test_convert_videos_zero_frames(self, mock_videocapture, mock_isfile, mock_exists):
        """Test convert_videos with a video with zero frames."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 0
        mock_videocapture.return_value = mock_cap
        node = VeoVideoToVHSNode()
        result = node.convert_videos(["zero_frames.mp4"])
        self.assertEqual(result[0].shape, (1, 512, 512, 3))

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("cv2.VideoCapture")
    @patch("cv2.cvtColor")
    def test_convert_videos_success(self, mock_cvtcolor, mock_videocapture, mock_isfile, mock_exists):
        """Test convert_videos with a valid video."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = [120, 1920, 1080]  # total_frames, width, height
        mock_cap.read.return_value = (True, np.zeros((1080, 1920, 3), dtype=np.uint8))
        mock_videocapture.return_value = mock_cap
        mock_cvtcolor.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        node = VeoVideoToVHSNode()
        result = node.convert_videos(["valid.mp4"])
        self.assertIsInstance(result[0], torch.Tensor)
        self.assertEqual(len(result[0].shape), 4) # (frames, height, width, channels)

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("moviepy.VideoFileClip")
    @patch("shutil.copy2")
    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    @patch("hashlib.md5")
    def test_preview_video_save(
        self, mock_md5, mock_open, mock_copy, mock_videofileclip, mock_isfile, mock_exists
    ):
        """Test preview_video with save_video=True."""
        mock_clip = MagicMock()
        mock_clip.duration = 10
        mock_clip.size = (1920, 1080)
        mock_videofileclip.return_value.__enter__.return_value = mock_clip
        mock_md5.return_value.hexdigest.return_value = "hash"

        node = VeoVideoSaveAndPreview()
        result = node.preview_video(
            video_paths=["valid.mp4"],
            autoplay=True,
            mute=True,
            loop=False,
            save_video=True,
            save_video_file_prefix="prefix",
        )
        self.assertIn("ui", result)
        self.assertIn("video", result["ui"])
        self.assertEqual(len(result["ui"]["video"]), 1)
        self.assertEqual(result["ui"]["video"][0]["type"], "output")
        mock_copy.assert_called_once()

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    @patch("moviepy.VideoFileClip")
    def test_preview_video_no_save(self, mock_videofileclip, mock_isfile, mock_exists):
        """Test preview_video with save_video=False."""
        mock_clip = MagicMock()
        mock_clip.duration = 10
        mock_clip.size = (1920, 1080)
        mock_videofileclip.return_value.__enter__.return_value = mock_clip

        node = VeoVideoSaveAndPreview()
        result = node.preview_video(
            video_paths=["valid.mp4"],
            autoplay=True,
            mute=True,
            loop=False,
            save_video=False,
            save_video_file_prefix="prefix",
        )
        self.assertIn("ui", result)
        self.assertIn("video", result["ui"])
        self.assertEqual(len(result["ui"]["video"]), 0)
        self.assertEqual(result["ui"]["video"][0]["type"], "temp")

    def test_preview_video_no_paths(self):
        """Test preview_video with no video paths."""
        node = VeoVideoSaveAndPreview()
        result = node.preview_video(
            video_paths=[],
            autoplay=True,
            mute=True,
            loop=False,
            save_video=False,
            save_video_file_prefix="prefix",
        )
        self.assertEqual(result["ui"]["video"], [])


    @patch("os.path.exists", return_value=False)
    def test_preview_video_non_existent_path(self, mock_exists):
        """Test preview_video with a non-existent video path."""
        node = VeoVideoSaveAndPreview()
        result = node.preview_video(
            video_paths=["non_existent.mp4"],
            autoplay=True,
            mute=True,
            loop=False,
            save_video=False,
            save_video_file_prefix="prefix",
        )
        self.assertIn("error", result["ui"])


    @patch("os.path.exists", return_value=True)
    @patch("os.path.isfile", return_value=True)
    def test_preview_video_unsupported_format(self, mock_isfile, mock_exists):
        """Test preview_video with an unsupported video format."""
        node = VeoVideoSaveAndPreview()
        result = node.preview_video(
            video_paths=["invalid.txt"],
            autoplay=True,
            mute=True,
            loop=False,
            save_video=False,
            save_video_file_prefix="prefix",
        )
        self.assertIn("error", result["ui"])


if __name__ == "__main__":
    unittest.main()