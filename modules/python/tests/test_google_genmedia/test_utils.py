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

"""Unit tests for utils.py"""
import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import torch
from PIL import Image
from src.custom_nodes.google_genmedia import utils
from src.custom_nodes.google_genmedia.exceptions import FileProcessingError


class TestUtils(unittest.TestCase):
    """Test cases for utils.py functions."""

    def test_tensor_to_pil_to_base64(self):
        """Test tensor_to_pil_to_base64 function."""
        tensor = torch.rand(1, 10, 10, 3)
        base64_string = utils.tensor_to_pil_to_base64(tensor)
        self.assertIsInstance(base64_string, str)

    def test_base64_to_pil_to_tensor(self):
        """Test base64_to_pil_to_tensor function."""
        image = Image.new("RGB", (10, 10))
        import base64
        import io

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_string = base64.b64encode(buffered.getvalue()).decode("utf-8")
        tensor = utils.base64_to_pil_to_tensor(base64_string)
        self.assertEqual(tensor.shape, (1, 10, 10, 4))

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_download_gcsuri_success(self, mock_storage_client):
        """Test download_gcsuri function success."""
        mock_blob = Mock()
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        result = utils.download_gcsuri("gs://bucket/path", "/tmp/path")
        self.assertTrue(result)
        mock_blob.download_to_filename.assert_called_once_with("/tmp/path")

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_download_gcsuri_exception(self, mock_storage_client):
        """Test download_gcsuri function with an exception during download."""
        mock_blob = Mock()
        mock_blob.download_to_filename.side_effect = Exception("Download failed")
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        with self.assertRaises(FileProcessingError):
            utils.download_gcsuri("gs://bucket/path", "/tmp/path")

    def test_download_gcsuri_invalid_uri(self):
        """Test download_gcsuri function with invalid URI."""
        with self.assertRaises(utils.exceptions.ConfigurationError):
            utils.download_gcsuri("invalid_uri", "/tmp/path")

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_and_image_success(self, mock_storage_client):
        """Test validate_gcs_uri_and_image function success."""
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.content_type = "image/png"
        mock_bucket = Mock()
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        valid, message = utils.validate_gcs_uri_and_image("gs://bucket/path")
        self.assertTrue(valid)

    def test_validate_gcs_uri_and_image_invalid_uri(self):
        """Test validate_gcs_uri_and_image function with invalid URI."""
        valid, message = utils.validate_gcs_uri_and_image("invalid_uri")
        self.assertFalse(valid)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_and_image_bucket_not_found(self, mock_storage_client):
        """Test validate_gcs_uri_and_image function with bucket not found."""
        mock_bucket = Mock()
        mock_bucket.exists.return_value = False
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        valid, message = utils.validate_gcs_uri_and_image("gs://bucket/path")
        self.assertFalse(valid)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_and_image_blob_not_found(self, mock_storage_client):
        """Test validate_gcs_uri_and_image function with blob not found."""
        mock_blob = Mock()
        mock_blob.exists.return_value = False
        mock_bucket = Mock()
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        valid, message = utils.validate_gcs_uri_and_image("gs://bucket/path")
        self.assertFalse(valid)

    @patch("src.custom_nodes.google_genmedia.utils.storage.Client")
    def test_validate_gcs_uri_and_image_not_an_image(self, mock_storage_client):
        """Test validate_gcs_uri_and_image function with a non-image file."""
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.content_type = "text/plain"
        mock_bucket = Mock()
        mock_bucket.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        valid, message = utils.validate_gcs_uri_and_image("gs://bucket/path")
        self.assertFalse(valid)

    @patch("builtins.open")
    @patch("os.path.exists", return_value=True)
    def test_media_file_to_genai_part_success(self, mock_exists, mock_open):
        """Test media_file_to_genai_part function success."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"file_bytes"
        part = utils.media_file_to_genai_part("/tmp/file", "image/png")
        self.assertIsNotNone(part)

    def test_media_file_to_genai_part_file_not_found(self):
        """Test media_file_to_genai_part function with file not found."""
        with self.assertRaises(FileNotFoundError):
            utils.media_file_to_genai_part("/tmp/non_existent_file", "image/png")

    @patch("os.path.exists", return_value=True)
    @patch("src.custom_nodes.google_genmedia.utils.media_file_to_genai_part")
    def test_prep_for_media_conversion_success(
        self, mock_media_file_to_genai_part, mock_exists
    ):
        """Test prep_for_media_conversion function success."""
        part = utils.prep_for_media_conversion("/tmp/file", "image/png")
        self.assertIsNotNone(part)

    @patch("os.path.exists", return_value=False)
    def test_prep_for_media_conversion_file_not_found(self, mock_exists):
        """Test prep_for_media_conversion function with file not found."""
        part = utils.prep_for_media_conversion("/tmp/non_existent_file", "image/png")
        self.assertIsNone(part)

    @patch("src.custom_nodes.google_genmedia.utils.download_gcsuri", return_value=True)
    @patch("os.makedirs")
    @patch("folder_paths.get_temp_directory", return_value="/tmp")
    def test_process_video_response_success(
        self, mock_get_temp_directory, mock_makedirs, mock_download
    ):
        """Test process_video_response function success."""
        mock_operation = MagicMock()
        mock_video = MagicMock()
        mock_video.video.uri = "gs://bucket/path"
        mock_operation.response.generated_videos = [mock_video]
        video_paths = utils.process_video_response(mock_operation)
        self.assertEqual(len(video_paths), 1)

    @patch("folder_paths.get_temp_directory", return_value="/tmp")
    def test_process_video_response_no_video_data(self, mock_get_temp_directory):
        """Test process_video_response function with no video data."""
        mock_operation = MagicMock()
        mock_operation.response.generated_videos = []
        with self.assertRaises(utils.exceptions.APICallError):
            utils.process_video_response(mock_operation)

    @patch(
        "src.custom_nodes.google_genmedia.utils.download_gcsuri",
        side_effect=FileProcessingError("Download failed"),
    )
    @patch("os.makedirs")
    @patch("folder_paths.get_temp_directory", return_value="/tmp")
    def test_process_video_response_download_failure(
        self, mock_get_temp_directory, mock_makedirs, mock_download
    ):
        """Test process_video_response function with a download failure."""
        mock_operation = MagicMock()
        mock_video = MagicMock()
        mock_video.video.uri = "gs://bucket/path"
        mock_operation.response.generated_videos = [mock_video]
        with self.assertRaises(utils.exceptions.APICallError):
            utils.process_video_response(mock_operation)

    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_image_from_text_success(self):
        """Test generate_image_from_text function success."""
        mock_client = Mock()
        mock_image = MagicMock()
        mock_image.image.image_bytes = b"image_bytes"
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        mock_client.models.generate_images.return_value = mock_response
        with patch("PIL.Image.open") as mock_open:
            images = utils.generate_image_from_text(
                client=mock_client,
                model="test-model",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )
            self.assertEqual(len(images), 1)
            mock_open.assert_called_once()

    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_image_from_text_no_images(self):
        """Test generate_image_from_text with no generated images."""
        mock_client = Mock()
        mock_response = MagicMock()
        mock_response.generated_images = []
        mock_client.models.generate_images.return_value = mock_response
        with self.assertRaises(utils.exceptions.APICallError):
            utils.generate_image_from_text(
                client=mock_client,
                model="test-model",
                prompt="a cat",
                person_generation="allow",
                aspect_ratio="1:1",
                number_of_images=1,
                negative_prompt="",
                seed=123,
                enhance_prompt=False,
                add_watermark=False,
                output_image_type="PNG",
                safety_filter_level="block_most",
            )

    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/video.mp4"],
    )
    @patch("time.sleep", return_value=None)
    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_video_from_text_success(self, mock_process_video, mock_sleep):
        """Test generate_video_from_text function success."""
        mock_client = Mock()
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_client.models.generate_videos.return_value = mock_operation
        mock_client.operations.get.return_value = mock_operation
        videos = utils.generate_video_from_text(
            client=mock_client,
            model="test-model",
            prompt="a cat",
            aspect_ratio="16:9",
            output_resolution="720p",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri=None,
            negative_prompt="",
            seed=123,
        )
        self.assertEqual(len(videos), 1)

    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/video.mp4"],
    )
    @patch("time.sleep", return_value=None)
    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_video_from_text_long_running(
        self, mock_process_video, mock_sleep
    ):
        """Test generate_video_from_text with a long-running operation."""
        mock_client = Mock()
        mock_operation_running = MagicMock()
        mock_operation_running.done = False
        mock_operation_done = MagicMock()
        mock_operation_done.done = True
        mock_client.models.generate_videos.return_value = mock_operation_running
        mock_client.operations.get.return_value = mock_operation_done
        videos = utils.generate_video_from_text(
            client=mock_client,
            model="test-model",
            prompt="a cat",
            aspect_ratio="16:9",
            output_resolution="720p",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            output_gcs_uri=None,
            negative_prompt="",
            seed=123,
        )
        self.assertEqual(len(videos), 1)
        mock_sleep.assert_called()

    @patch(
        "src.custom_nodes.google_genmedia.utils.tensor_to_pil_to_base64",
        return_value="base64_string",
    )
    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/video.mp4"],
    )
    @patch("time.sleep", return_value=None)
    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_video_from_image_with_last_frame(
        self, mock_tensor_to_base64, mock_process_video, mock_sleep
    ):
        """Test generate_video_from_image with a last_frame."""
        mock_client = Mock()
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_client.models.generate_videos.return_value = mock_operation
        mock_client.operations.get.return_value = mock_operation
        videos = utils.generate_video_from_image(
            client=mock_client,
            model="test-model",
            image=torch.rand(1, 10, 10, 3),
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            output_resolution="720p",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            last_frame=torch.rand(1, 10, 10, 3),
            output_gcs_uri=None,
            negative_prompt="",
            seed=123,
        )
        self.assertEqual(len(videos), 1)

    @patch(
        "src.custom_nodes.google_genmedia.utils.validate_gcs_uri_and_image",
        return_value=(True, ""),
    )
    @patch(
        "src.custom_nodes.google_genmedia.utils.process_video_response",
        return_value=["/tmp/video.mp4"],
    )
    @patch("time.sleep", return_value=None)
    @patch("src.custom_nodes.google_genmedia.utils.retry_on_api_error", lambda x: x)
    def test_generate_video_from_gcsuri_image_with_last_frame(
        self, mock_validate_gcs, mock_process_video, mock_sleep
    ):
        """Test generate_video_from_gcsuri_image with a last_frame_gcsuri."""
        mock_client = Mock()
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_client.models.generate_videos.return_value = mock_operation
        mock_client.operations.get.return_value = mock_operation
        videos = utils.generate_video_from_gcsuri_image(
            client=mock_client,
            model="test-model",
            gcsuri="gs://bucket/path",
            image_format="PNG",
            prompt="a cat",
            aspect_ratio="16:9",
            output_resolution="720p",
            compression_quality="optimized",
            person_generation="allow",
            duration_seconds=5,
            generate_audio=False,
            enhance_prompt=False,
            sample_count=1,
            last_frame_gcsuri="gs://bucket/last_frame.png",
            output_gcs_uri=None,
            negative_prompt="",
            seed=123,
        )
        self.assertEqual(len(videos), 1)

    @patch(
        "src.custom_nodes.google_genmedia.utils.validate_gcs_uri_and_image",
        return_value=(False, "Invalid GCS URI"),
    )
    def test_generate_video_from_gcsuri_image_validation_failure(
        self, mock_validate_gcs
    ):
        """Test generate_video_from_gcsuri_image with a validation failure."""
        mock_client = Mock()
        with self.assertRaises(utils.exceptions.ConfigurationError):
            utils.generate_video_from_gcsuri_image(
                client=mock_client,
                model="test-model",
                gcsuri="gs://invalid",
                image_format="PNG",
                prompt="a cat",
                aspect_ratio="16:9",
                output_resolution="720p",
                compression_quality="optimized",
                person_generation="allow",
                duration_seconds=5,
                generate_audio=False,
                enhance_prompt=False,
                sample_count=1,
                last_frame_gcsuri=None,
                output_gcs_uri=None,
                negative_prompt="",
                seed=123,
            )


if __name__ == "__main__":
    unittest.main()