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
        reconstructed_image = Image.open(io.BytesIO(base64.b64decode(base64_string)))
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
    def test_prep_for_media_conversion_file_not_found(self, mock_exists):
        result = utils.prep_for_media_conversion("/fake/path.png", "image/png")
        self.assertIsNone(result)

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

    @patch("src.custom_nodes.google_genmedia.utils.os.makedirs")
    def test_process_video_response_no_videos_found(self, mock_makedirs):
        """Tests that a RuntimeError is raised when no video data is in the response."""
        # Arrange
        mock_operation = MagicMock()
        mock_operation.response = {}
        mock_operation.result = None

        # Act & Assert
        with self.assertRaisesRegex(RuntimeError, "No video data found"):
            utils.process_video_response(mock_operation)

    @patch(
        "src.custom_nodes.google_genmedia.utils.folder_paths.get_temp_directory",
        return_value="/tmp/fake_temp_dir",
    )
    @patch("src.custom_nodes.google_genmedia.utils.download_gcsuri", return_value=True)
    def test_process_video_response_with_gcs_uri(self, mock_download, mock_get_temp):
        """Tests processing a response where the video is a GCS URI."""
        # Arrange
        mock_video = MagicMock()
        mock_video.video.uri = "gs://my-bucket/my-video.mp4"
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

    # --- Tests for generate_image_from_text ---

    @patch("src.custom_nodes.google_genmedia.utils.genai.Client")
    def test_generate_image_from_text_success(self, mock_client):
        # Arrange
        mock_image = MagicMock()
        mock_image.image.image_bytes = b"fake_image_bytes"

        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        mock_client.models.generate_images.return_value = mock_response

        # Act
        with patch(
            "src.custom_nodes.google_genmedia.utils.PIL_Image.open"
        ) as mock_pil_open:
            images = utils.generate_image_from_text(
                client=mock_client,
                model="imagen3",
                prompt="a cat",
                person_generation="ALLOW_ADULT",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=None,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="png",
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
                retry_count=0,
                retry_delay=0,
            )

            # Assert
            self.assertEqual(len(images), 1)
            mock_pil_open.assert_called_once()
            self.assertEqual(mock_pil_open.call_args[0][0].read(), b"fake_image_bytes")

    @patch("src.custom_nodes.google_genmedia.utils.genai.Client")
    def test_generate_image_from_text_resource_exhausted(self, mock_client):
        # Arrange
        error = genai_errors.ClientError("resource exhausted", response_json={})
        error.code = StatusCode.RESOURCE_EXHAUSTED
        mock_client.models.generate_images.side_effect = error

        # Act & Assert
        with self.assertRaises(RuntimeError):
            utils.generate_image_from_text(
                client=mock_client,
                model="imagen3",
                prompt="a cat",
                person_generation="ALLOW_ADULT",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=None,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="png",
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
                retry_count=1,
                retry_delay=0,
            )

    # --- Tests for generate_video_from_text ---

    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/fake.mp4"],
    )
    @patch("src.custom_nodes.google_genmedia.utils.genai.Client")
    def test_generate_video_from_text_success(self, mock_client, mock_process_video):
        # Arrange
        mock_operation = MagicMock()
        mock_operation.done.return_value = True
        mock_client.models.generate_videos.return_value = mock_operation

        # Act
        video_paths = utils.generate_video_from_text(
            client=mock_client,
            model="veo",
            prompt="a cat",
            aspect_ratio="1:1",
            output_resolution="1080p",
            compression_quality="optimized",
            person_generation="ALLOW_ADULT",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri=None,
            negative_prompt=None,
            seed=None,
            retry_count=0,
            retry_delay=0,
        )

        # Assert
        self.assertEqual(video_paths, ["/tmp/fake.mp4"])
        mock_client.operations.get.assert_not_called()  # Should not poll if done

    @patch("src.custom_nodes.google_genmedia.utils.genai.Client")
    def test_generate_video_from_text_invalid_argument(self, mock_client):
        # Arrange
        error = genai_errors.ClientError("invalid argument", response_json={})
        error.code = StatusCode.INVALID_ARGUMENT
        mock_client.models.generate_videos.side_effect = error

        # Act & Assert
        with self.assertRaises(ValueError):
            utils.generate_video_from_text(
                client=mock_client,
                model="veo",
                prompt="a cat",
                aspect_ratio="1:1",
                output_resolution="1080p",
                compression_quality="optimized",
                person_generation="ALLOW_ADULT",
                duration_seconds=5,
                generate_audio=False,
                enhance_prompt=False,
                sample_count=1,
                output_gcs_uri=None,
                negative_prompt=None,
                seed=None,
                retry_count=0,
                retry_delay=0,
            )

    # --- Tests for generate_video_from_gcsuri_image ---

    @patch("src.custom_nodes.google_genmedia.utils.validate_gcs_uri_and_image")
    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/fake.mp4"],
    )
    @patch("src.custom_nodes.google_genmedia.utils.genai.Client")
    def test_generate_video_from_gcsuri_image_success(
        self, mock_client, mock_process_video, mock_validate_gcs
    ):
        # Arrange
        mock_validate_gcs.return_value = (True, "Valid URI message")
        mock_operation = MagicMock()
        mock_operation.done.return_value = True
        mock_client.models.generate_videos.return_value = mock_operation

        # Act
        video_paths = utils.generate_video_from_gcsuri_image(
            client=mock_client,
            model="veo-2.0",
            gcsuri="gs://my-bucket/my-image.png",
            image_format="image/png",
            prompt="a cat",
            aspect_ratio="1:1",
            output_resolution="1080p",
            compression_quality="optimized",
            person_generation="ALLOW_ADULT",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            last_frame_gcsuri=None,
            output_gcs_uri=None,
            negative_prompt=None,
            seed=None,
            retry_count=0,
            retry_delay=0,
        )

        # Assert
        self.assertEqual(video_paths, ["/tmp/fake.mp4"])


if __name__ == "__main__":
    unittest.main()
