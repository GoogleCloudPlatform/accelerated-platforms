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

"""Unit tests for retry.py"""

import unittest
from unittest.mock import patch, MagicMock

from src.custom_nodes.google_genmedia.retry import retry_on_api_error


class TestRetryDecorator(unittest.TestCase):
    """Test cases for the retry_on_api_error decorator."""

    def test_no_retry_on_success(self):
        """Test that the decorated function is called once on success."""
        mock_func = MagicMock()
        decorated_func = retry_on_api_error()(mock_func)
        decorated_func()
        mock_func.assert_called_once()


if __name__ == "__main__":
    unittest.main()
