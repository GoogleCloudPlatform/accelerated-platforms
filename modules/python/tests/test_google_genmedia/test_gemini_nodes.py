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

"""Unit tests for gemini_nodes.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.gemini_nodes import GeminiNode25


class TestGeminiNode25(unittest.TestCase):
    """Test cases for GeminiNode25 class."""

    @patch("src.custom_nodes.google_genmedia.gemini_nodes.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.gemini_nodes.genai.Client")
    def test_initialization(self, mock_genai_client, mock_get_gcp_metadata):
        """Test that the node can be initialized."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        node = GeminiNode25()
        self.assertIsNotNone(node)


if __name__ == "__main__":
    unittest.main()