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

# --- 2. Set up all the mocks (Forceful Version) ---
# We are *forcefully* overwriting sys.modules to ensure
# our mocks are used, not the real libraries.

google_mock = MagicMock()
google_mock.__path__ = []
google_mock.__spec__ = MagicMock()
sys.modules["google"] = google_mock

genai_mock = MagicMock()
genai_mock.__path__ = []
genai_mock.__spec__ = MagicMock()
sys.modules["google.genai"] = genai_mock
sys.modules["google.genai.types"] = MagicMock(__spec__=MagicMock())
sys.modules["google.genai.errors"] = MagicMock(__spec__=MagicMock())

cloud_mock = MagicMock()
cloud_mock.__path__ = []
cloud_mock.__spec__ = MagicMock()
sys.modules["google.cloud"] = cloud_mock

storage_mock = MagicMock()
storage_mock.__path__ = []
storage_mock.__spec__ = MagicMock()
sys.modules["google.cloud.storage"] = storage_mock

api_core_mock = MagicMock()
api_core_mock.__path__ = []
api_core_mock.__spec__ = MagicMock()
sys.modules["google.api_core"] = api_core_mock

# Mock sub-modules of google.api_core
api_core_client_info_mock = MagicMock(__spec__=MagicMock())
api_core_mock.client_info = api_core_client_info_mock
sys.modules["google.api_core.client_info"] = api_core_client_info_mock

gapic_v1_mock = MagicMock(__path__=[], __spec__=MagicMock())
api_core_mock.gapic_v1 = gapic_v1_mock
sys.modules["google.api_core.gapic_v1"] = gapic_v1_mock

gapic_client_info_mock = MagicMock(__spec__=MagicMock())
gapic_v1_mock.client_info = gapic_client_info_mock
sys.modules["google.api_core.gapic_v1.client_info"] = gapic_client_info_mock

# --- ADD THIS BLOCK FOR THE NEW ERROR ---
client_options_mock = MagicMock(__spec__=MagicMock())
api_core_mock.client_options = client_options_mock
sys.modules["google.api_core.client_options"] = client_options_mock
# --- END OF NEW BLOCK ---

folder_paths_mock = MagicMock()
folder_paths_mock.__spec__ = MagicMock()
sys.modules["folder_paths"] = folder_paths_mock
