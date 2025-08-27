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
from unittest.mock import patch, MagicMock, mock_open
import torch
import numpy as np
from PIL import Image
import base64
import io
import sys
from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors
from grpc import StatusCode

sys.modules["folder_paths"] = MagicMock()

from src.custom_nodes.google_genmedia import utils


class TestUtils(unittest.TestCase):
    def test_tensor_to_pil_to_base64_and_back(self):
        # Create a tensor
        tensor = torch.rand(1, 10, 10, 3)

        # Convert to base64
        base64_string = utils.tensor_to_pil_to_base64(tensor, format="PNG")
        self.assertIsInstance(base64_string, str)

        # Convert back to tensor
        decoded_tensor = utils.base64_to_pil_to_tensor(base64_string)
        self.assertIsInstance(decoded_tensor, torch.Tensor)

        # Check if shapes are similar (RGBA vs RGB)
        self.assertEqual(decoded_tensor.shape[0], 1)
        self.assertEqual(decoded_tensor.shape[1], 10)
        self.assertEqual(decoded_tensor.shape[2], 10)
        self.assertEqual(decoded_tensor.shape[3], 4)  # RGBA

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_and_image_success(self, mock_storage_client):
        # Arrange
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.content_type = "image/png"
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act
        is_valid, message = utils.validate_gcs_uri_and_image(
            "gs://my-bucket/my-image.png"
        )

        # Assert
        self.assertTrue(is_valid)
        self.assertIn("is a valid image", message)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_invalid_format(self, mock_storage_client):
        # Act
        is_valid, message = utils.validate_gcs_uri_and_image("not-a-gcs-uri")
        # Assert
        self.assertFalse(is_valid)
        self.assertIn("Invalid GCS URI format", message)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_download_gcsuri_success(self, mock_storage_client):
        # Arrange
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act
        result = utils.download_gcsuri("gs://my-bucket/my-file.txt", "/tmp/file.txt")

        # Assert
        self.assertTrue(result)
        mock_blob.download_to_filename.assert_called_once_with("/tmp/file.txt")

    @patch("src.custom_nodes.google_genmedia.utils.media_file_to_genai_part")
    @patch("os.path.exists", return_value=True)
    def test_prep_for_media_conversion_success(
        self, mock_exists, mock_media_file_to_genai_part
    ):
        mock_part = MagicMock()
        mock_media_file_to_genai_part.return_value = mock_part

        result = utils.prep_for_media_conversion("/fake/path.png", "image/png")

        self.assertEqual(result, mock_part)
        mock_media_file_to_genai_part.assert_called_once_with(
            "/fake/path.png", "image/png"
        )

    @patch("os.path.exists", return_value=False)
    def test_prep_for_media_conversion_file_not_found(self, mock_exists):
        result = utils.prep_for_media_conversion("/fake/path.png", "image/png")
        self.assertIsNone(result)

    # --- Additional tests for tensor_to_pil_to_base64 ---

    def test_tensor_to_pil_to_base64_with_pil_image(self):
        """Tests the case where the input is already a PIL Image."""
        # Arrange
        pil_image = Image.new("RGB", (10, 10), color="red")

        # Act
        base64_string = utils.tensor_to_pil_to_base64(pil_image, format="JPEG")

        # Assert
        self.assertIsInstance(base64_string, str)
        # Decode to check if it's a valid image
        decoded_data = base64.b64decode(base64_string)
        reconstructed_image = Image.open(io.BytesIO(decoded_data))
        self.assertEqual(reconstructed_image.format, "JPEG")

    # --- Additional tests for download_gcsuri ---

    def test_download_gcsuri_invalid_uri_no_prefix(self):
        """Tests that download_gcsuri raises ValueError for URIs without 'gs://'."""
        with self.assertRaisesRegex(ValueError, "Invalid GCS URI format"):
            utils.download_gcsuri("my-bucket/my-file.txt", "/tmp/file.txt")

    def test_download_gcsuri_invalid_uri_no_object(self):
        """Tests that download_gcsuri raises ValueError for URIs without an object path."""
        with self.assertRaisesRegex(ValueError, "No object path specified"):
            utils.download_gcsuri("gs://my-bucket", "/tmp/file.txt")

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_download_gcsuri_download_fails(self, mock_storage_client):
        """Tests that download_gcsuri raises RuntimeError on download failure."""
        # Arrange
        mock_blob = MagicMock()
        mock_blob.download_to_filename.side_effect = Exception("Permission denied")
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act & Assert
        with self.assertRaisesRegex(RuntimeError, "Error downloading"):
            utils.download_gcsuri("gs://my-bucket/my-file.txt", "/tmp/file.txt")

    # --- Tests for media_file_to_genai_part ---

    @patch("src.custom_nodes.google_genmedia.utils.types.Part")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_media_bytes")
    @patch("os.path.exists", return_value=True)
    def test_media_file_to_genai_part_success(self, mock_exists, mock_file, mock_part):
        """Tests successful conversion of a media file to a genai Part."""
        # Act
        utils.media_file_to_genai_part("/fake/path.mp4", "video/mp4")

        # Assert
        mock_file.assert_called_with("/fake/path.mp4", "rb")
        mock_part.from_bytes.assert_called_with(
            data=b"fake_media_bytes", mime_type="video/mp4"
        )

    @patch("os.path.exists", return_value=False)
    def test_media_file_to_genai_part_file_not_found(self, mock_exists):
        """Tests that FileNotFoundError is raised if the file does not exist."""
        with self.assertRaises(FileNotFoundError):
            utils.media_file_to_genai_part("/fake/path.mp4", "video/mp4")

    # --- Additional tests for validate_gcs_uri_and_image ---

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_bucket_not_found(self, mock_storage_client):
        """Tests the case where the GCS bucket does not exist."""
        # Arrange
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = False
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act
        is_valid, message = utils.validate_gcs_uri_and_image(
            "gs://non-existent-bucket/img.png"
        )

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("does not exist or is inaccessible", message)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_object_not_found(self, mock_storage_client):
        """Tests the case where the GCS object does not exist in the bucket."""
        # Arrange
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act
        is_valid, message = utils.validate_gcs_uri_and_image(
            "gs://my-bucket/non-existent-object.png"
        )

        # Assert
        self.assertFalse(is_valid)
        self.assertIn("not found in bucket", message)

    # --- Tests for process_video_response ---

    def test_process_video_response_no_videos_found(self):
        """Tests that a RuntimeError is raised when no video data is in the response."""
        # Arrange
        mock_operation = MagicMock()
        mock_operation.response = {}  # Empty response
        mock_operation.result = None

        # Act & Assert
        with self.assertRaisesRegex(RuntimeError, "No video data found"):
            utils.process_video_response(mock_operation)

    # UPDATED DECORATOR: Added a patch for folder_paths to return a real path
    @patch(
        "src.custom_nodes.google_genmedia.utils.folder_paths.get_temp_directory",
        return_value="/tmp/fake_temp_dir",
    )
    @patch("src.custom_nodes.google_genmedia.utils.download_gcsuri", return_value=True)
    # UPDATED SIGNATURE: Added the new mock argument from the patch
    def test_process_video_response_with_gcs_uri(self, mock_download, mock_get_temp):
        """Tests processing a response where the video is a GCS URI."""
        # Arrange
        mock_video = MagicMock()
        mock_video.video.uri = "gs://my-bucket/my-video.mp4"
        # Clear the 'save' attribute to ensure the URI path is taken
        del mock_video.video.save

        mock_operation = MagicMock()
        mock_operation.response.generated_videos = [mock_video]

        # Act
        video_paths = utils.process_video_response(mock_operation)

        # Assert
        self.assertEqual(len(video_paths), 1)
        mock_download.assert_called_once_with(
            "gs://my-bucket/my-video.mp4", unittest.mock.ANY
        )


if __name__ == "__main__":
    unittest.main()
