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

"""Unit tests for config.py"""

import unittest
from unittest.mock import Mock, patch

from src.custom_nodes.google_genmedia.config import get_gcp_metadata


class TestConfigModule(unittest.TestCase):
    """Test cases for config module functions."""

    @patch("requests.get")
    def test_get_gcp_metadata_success(self, mock_get):
        """Test successful metadata retrieval."""
        # Setup mock response
        mock_response = Mock()
        mock_response.text = "test-project-123"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Verify the result
        self.assertEqual(result, "test-project-123")

        # Verify the request was made correctly
        mock_get.assert_called_once_with(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )

    @patch("requests.get")
    def test_get_gcp_metadata_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        from requests.exceptions import HTTPError

        # Setup mock to raise HTTPError
        mock_get.side_effect = HTTPError("404 Not Found")

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Should return None on error
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_gcp_metadata_timeout(self, mock_get):
        """Test handling of timeout errors."""
        from requests.exceptions import Timeout

        # Setup mock to raise Timeout
        mock_get.side_effect = Timeout("Request timed out")

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Should return None on timeout
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_gcp_metadata_connection_error(self, mock_get):
        """Test handling of connection errors."""
        from requests.exceptions import ConnectionError

        # Setup mock to raise ConnectionError
        mock_get.side_effect = ConnectionError("Connection failed")

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Should return None on connection error
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_gcp_metadata_request_exception(self, mock_get):
        """Test handling of general request exceptions."""
        from requests.exceptions import RequestException

        # Setup mock to raise RequestException
        mock_get.side_effect = RequestException("General request error")

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Should return None on request exception
        self.assertIsNone(result)

    @patch("requests.get")
    def test_get_gcp_metadata_strips_whitespace(self, mock_get):
        """Test that returned text is properly stripped of whitespace."""
        # Setup mock response with whitespace
        mock_response = Mock()
        mock_response.text = "  test-project-123  \n"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        result = get_gcp_metadata("project/project-id")

        # Verify whitespace is stripped
        self.assertEqual(result, "test-project-123")

    @patch("requests.get")
    def test_get_gcp_metadata_different_paths(self, mock_get):
        """Test metadata retrieval with different paths."""
        # Setup mock response
        mock_response = Mock()
        mock_response.text = "us-central1-a"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Test different path
        result = get_gcp_metadata("instance/zone")

        # Verify the result
        self.assertEqual(result, "us-central1-a")

        # Verify the correct URL was called
        mock_get.assert_called_once_with(
            "http://metadata.google.internal/computeMetadata/v1/instance/zone",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )


if __name__ == "__main__":
    unittest.main()
