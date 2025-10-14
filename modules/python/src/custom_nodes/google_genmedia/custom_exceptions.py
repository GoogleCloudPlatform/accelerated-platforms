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

# This is a preview version of Google GenAI custom nodes


class ComfyUINodeError(Exception):
    """Base exception for all Google GenAI ComfyUI node errors."""

    pass


class ConfigurationError(ComfyUINodeError):
    """Raised when the client fails to initialize due to missing config,
    GCP project ID/region issues, or authentication problems."""

    pass


class APIInputError(ComfyUINodeError):
    """Raised when a user-provided input parameter or prompt violates
    API constraints (e.g., invalid aspect ratio, bad prompt, local file not found)."""

    pass


class APIExecutionError(ComfyUINodeError):
    """Raised for transient or service-related failures during an API call
    (e.g., quota exceeded, permission denied, internal server error)."""

    pass
