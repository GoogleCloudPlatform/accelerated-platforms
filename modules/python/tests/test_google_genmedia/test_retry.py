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
from src.custom_nodes.google_genmedia import exceptions
from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors


class TestRetryDecorator(unittest.TestCase):
    """Test cases for the retry_on_api_error decorator."""

    def test_no_retry_on_success(self):
        """Test that the decorated function is called once on success."""
        mock_func = MagicMock()
        decorated_func = retry_on_api_error()(mock_func)
        decorated_func()
        mock_func.assert_called_once()

    @patch("time.sleep", return_value=None)
    def test_retry_on_resource_exhausted(self, mock_sleep):
        """Test retry on ResourceExhausted error."""
        mock_func = MagicMock()
        mock_func.side_effect = [
            api_core_exceptions.ResourceExhausted("test"),
            "success",
        ]
        decorated_func = retry_on_api_error()(mock_func)
        result = decorated_func()
        self.assertEqual(mock_func.call_count, 2)
        self.assertEqual(result, "success")

    @patch("time.sleep", return_value=None)
    def test_retry_on_service_unavailable(self, mock_sleep):
        """Test retry on ServiceUnavailable error."""
        mock_func = MagicMock()
        mock_func.side_effect = [
            api_core_exceptions.ServiceUnavailable("test"),
            "success",
        ]
        decorated_func = retry_on_api_error()(mock_func)
        result = decorated_func()
        self.assertEqual(mock_func.call_count, 2)
        self.assertEqual(result, "success")

    @patch("time.sleep", return_value=None)
    def test_retry_on_server_error(self, mock_sleep):
        """Test retry on ServerError error."""
        mock_func = MagicMock()
        mock_func.side_effect = [genai_errors.ServerError("test"), "success"]
        decorated_func = retry_on_api_error()(mock_func)
        result = decorated_func()
        self.assertEqual(mock_func.call_count, 1)
        self.assertEqual(result, "success")

    @patch("time.sleep", return_value=None)
    def test_max_retries_exceeded(self, mock_sleep):
        """Test that it gives up after max_retries."""
        mock_func = MagicMock()
        mock_func.side_effect = api_core_exceptions.ResourceExhausted("test")
        decorated_func = retry_on_api_error(max_retries=3)(mock_func)
        with self.assertRaises(exceptions.APICallError):
            decorated_func()
        self.assertEqual(mock_func.call_count, 4)  # 1 initial call + 3 retries

    def test_invalid_argument_error(self):
        """Test that it raises ConfigurationError on InvalidArgument."""
        mock_func = MagicMock()
        mock_func.side_effect = api_core_exceptions.InvalidArgument("test")
        decorated_func = retry_on_api_error()(mock_func)
        with self.assertRaises(exceptions.ConfigurationError):
            decorated_func()

    def test_permission_denied_error(self):
        """Test that it raises APICallError on PermissionDenied."""
        mock_func = MagicMock()
        mock_func.side_effect = api_core_exceptions.PermissionDenied("test")
        decorated_func = retry_on_api_error()(mock_func)
        with self.assertRaises(exceptions.APICallError):
            decorated_func()

    def test_deadline_exceeded_error(self):
        """Test that it raises APICallError on DeadlineExceeded."""
        mock_func = MagicMock()
        mock_func.side_effect = api_core_exceptions.DeadlineExceeded("test")
        decorated_func = retry_on_api_error()(mock_func)
        with self.assertRaises(exceptions.APICallError):
            decorated_func()

    def test_google_api_call_error(self):
        """Test that it raises APICallError on GoogleAPICallError."""
        mock_func = MagicMock()
        mock_func.side_effect = api_core_exceptions.GoogleAPICallError("test")
        decorated_func = retry_on_api_error()(mock_func)
        with self.assertRaises(exceptions.APICallError):
            decorated_func()


if __name__ == "__main__":
    unittest.main()
