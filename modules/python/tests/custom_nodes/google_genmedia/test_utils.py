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
from PIL import Image
import base64
import io
import sys
from unittest.mock import MagicMock
sys.modules['folder_paths'] = MagicMock()

from src.custom_nodes.google_genmedia import utils

class TestUtils(unittest.TestCase):

    def test_tensor_to_pil_to_base64_and_back(self):
        # Create a tensor
        tensor = torch.rand(1, 10, 10, 3)
        
        # Convert to base64
        base64_string = utils.tensor_to_pil_to_base64(tensor, format='PNG')
        self.assertIsInstance(base64_string, str)

        # Convert back to tensor
        decoded_tensor = utils.base64_to_pil_to_tensor(base64_string)
        self.assertIsInstance(decoded_tensor, torch.Tensor)
        
        # Check if shapes are similar (RGBA vs RGB)
        self.assertEqual(decoded_tensor.shape[0], 1)
        self.assertEqual(decoded_tensor.shape[1], 10)
        self.assertEqual(decoded_tensor.shape[2], 10)
        self.assertEqual(decoded_tensor.shape[3], 4) # RGBA

    @patch('src.custom_nodes.google_genmedia.utils.storage.Client')
    def test_validate_gcs_uri_and_image_success(self, mock_storage_client):
        # Arrange
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.content_type = 'image/png'
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        # Act
        is_valid, message = utils.validate_gcs_uri_and_image("gs://my-bucket/my-image.png")

        # Assert
        self.assertTrue(is_valid)
        self.assertIn("is a valid image", message)

    @patch('src.custom_nodes.google_genmedia.utils.storage.Client')
    def test_validate_gcs_uri_invalid_format(self, mock_storage_client):
        # Act
        is_valid, message = utils.validate_gcs_uri_and_image("not-a-gcs-uri")
        # Assert
        self.assertFalse(is_valid)
        self.assertIn("Invalid GCS URI format", message)

    @patch('src.custom_nodes.google_genmedia.utils.storage.Client')
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

    @patch('src.custom_nodes.google_genmedia.utils.media_file_to_genai_part')
    @patch('os.path.exists', return_value=True)
    def test_prep_for_media_conversion_success(self, mock_exists, mock_media_file_to_genai_part):
        mock_part = MagicMock()
        mock_media_file_to_genai_part.return_value = mock_part
        
        result = utils.prep_for_media_conversion("/fake/path.png", "image/png")
        
        self.assertEqual(result, mock_part)
        mock_media_file_to_genai_part.assert_called_once_with("/fake/path.png", "image/png")

    @patch('os.path.exists', return_value=False)
    def test_prep_for_media_conversion_file_not_found(self, mock_exists):
        result = utils.prep_for_media_conversion("/fake/path.png", "image/png")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()