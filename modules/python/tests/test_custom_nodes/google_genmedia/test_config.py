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

import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.config import get_gcp_metadata


class TestConfig(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.config.requests.get")
    def test_get_gcp_metadata_success(self, mock_get):
        """
        Tests that get_gcp_metadata returns the project ID on a successful API call.
        """
        # Arrange
        mock_response = Mock()
        mock_response.text = "test-project-id "
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Act
        result = get_gcp_metadata("project/project-id")

        # Assert
        self.assertEqual(result, "test-project-id")
        mock_get.assert_called_once_with(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )

    @patch("src.custom_nodes.google_genmedia.config.requests.get")
    def test_get_gcp_metadata_failure(self, mock_get):
        """
        Tests that get_gcp_metadata returns None when the API call fails.
        """
        # Arrange
        mock_get.side_effect = requests.exceptions.RequestException("Test error")

        # Act
        result = get_gcp_metadata("project/project-id")

        # Assert
        self.assertIsNone(result)
        mock_get.assert_called_once_with(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
