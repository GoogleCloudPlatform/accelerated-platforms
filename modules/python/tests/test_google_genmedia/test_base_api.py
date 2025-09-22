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

"""Unit tests for base_api.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.base_api import GoogleGenAIBaseAPI


class TestGoogleGenAIBaseAPI(unittest.TestCase):
    """Test cases for GoogleGenAIBaseAPI class."""

    @patch("src.custom_nodes.google_genmedia.base_api.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.base_api.genai.Client")
    def test_initialization(self, mock_genai_client, mock_get_gcp_metadata):
        """Test that the API client can be initialized."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        api = GoogleGenAIBaseAPI()
        self.assertIsNotNone(api)


if __name__ == "__main__":
    unittest.main()
