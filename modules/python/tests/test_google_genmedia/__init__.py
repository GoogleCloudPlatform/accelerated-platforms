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

import types
import os
import sys
from unittest.mock import MagicMock

print("--- Running test_google_genmedia __init__.py ---")

test_dir = os.path.dirname(os.path.abspath(__file__))
print("test_dir:", {test_dir})

python_root = os.path.abspath(os.path.join(test_dir, "..", ".."))
print("python root:", {python_root})

if python_root not in sys.path:
    sys.path.insert(0, python_root)

# Mock google.api_core.exceptions and its exceptions
api_core_exceptions_mock = MagicMock()
api_core_exceptions_mock.GoogleAPICallError = type(
    "GoogleAPICallError", (Exception,), {}
)
api_core_exceptions_mock.ResourceExhausted = type(
    "ResourceExhausted", (api_core_exceptions_mock.GoogleAPICallError,), {}
)
api_core_exceptions_mock.ServiceUnavailable = type(
    "ServiceUnavailable", (api_core_exceptions_mock.GoogleAPICallError,), {}
)
api_core_exceptions_mock.InvalidArgument = type(
    "InvalidArgument", (api_core_exceptions_mock.GoogleAPICallError,), {}
)
api_core_exceptions_mock.PermissionDenied = type(
    "PermissionDenied", (api_core_exceptions_mock.GoogleAPICallError,), {}
)
api_core_exceptions_mock.DeadlineExceeded = type(
    "DeadlineExceeded", (api_core_exceptions_mock.GoogleAPICallError,), {}
)
sys.modules["google.api_core.exceptions"] = api_core_exceptions_mock

google_mock = MagicMock()
google_mock.__path__ = []
google_mock.__spec__ = MagicMock()
sys.modules["google"] = google_mock

genai_mock = MagicMock()
genai_mock.__path__ = []
genai_mock.__spec__ = MagicMock()
sys.modules["google.genai"] = genai_mock
sys.modules["google.genai.types"] = MagicMock(__spec__=MagicMock())

# Mock google.genai.errors and its APIError and ServerError exception
genai_errors_mock = types.ModuleType("google.genai.errors")
genai_errors_mock.APIError = type("APIError", (Exception,), {})
genai_errors_mock.ServerError = type("ServerError", (Exception,), {})
sys.modules["google.genai.errors"] = genai_errors_mock


cloud_mock = MagicMock()
cloud_mock.__path__ = []
cloud_mock.__spec__ = MagicMock()
sys.modules["google.cloud"] = cloud_mock

storage_mock = MagicMock()
storage_mock.__path__ = []
storage_mock.__spec__ = MagicMock()
sys.modules["google.cloud.storage"] = storage_mock


# Mock sub-modules of google.api_core
api_core_client_info_mock = MagicMock(__spec__=MagicMock())
sys.modules["google.api_core.client_info"] = api_core_client_info_mock

gapic_v1_mock = MagicMock(__path__=[], __spec__=MagicMock())
sys.modules["google.api_core.gapic_v1"] = gapic_v1_mock

gapic_client_info_mock = MagicMock(__spec__=MagicMock())
gapic_v1_mock.client_info = gapic_client_info_mock
sys.modules["google.api_core.gapic_v1.client_info"] = gapic_client_info_mock

# --- ADD THIS BLOCK FOR THE NEW ERROR ---
client_options_mock = MagicMock(__spec__=MagicMock())
sys.modules["google.api_core.client_options"] = client_options_mock
# --- END OF NEW BLOCK ---

cv2_mock = MagicMock()

sys.modules["cv2"] = cv2_mock

moviepy_mock = MagicMock()
sys.modules["moviepy"] = moviepy_mock

folder_paths_mock = MagicMock()
folder_paths_mock.__spec__ = MagicMock()
sys.modules["folder_paths"] = folder_paths_mock

import os
import unittest


def load_tests(loader, tests, pattern):
    """
    This function is automatically called by unittest when
    it loads this package.
    """
    # Get the path to this directory
    this_dir = os.path.dirname(os.path.abspath(__file__))

    # Use the loader's 'discover' method to find all tests
    # (files matching 'test*.py') in this directory.
    discovered_tests = loader.discover(start_dir=this_dir, pattern="test*.py")

    # Add all discovered tests to a new TestSuite
    suite = unittest.TestSuite()
    suite.addTests(discovered_tests)
    return suite
