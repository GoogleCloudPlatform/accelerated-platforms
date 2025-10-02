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

"""Custom exceptions for Google GenMedia custom nodes.

This module provides a hierarchy of exceptions for different failure scenarios:
- APIInitializationError: Client setup failures
- APICallError: Runtime API call failures
- ConfigurationError: Invalid parameters or settings
- FileProcessingError: File I/O or format issues

All exceptions inherit from GoogleGenMediaException and support exception chaining
to preserve the original error context.
"""

from typing import Optional


class GoogleGenMediaException(Exception):
    """Base exception for the Google GenMedia custom nodes.

    This base class provides a simple interface for custom exceptions with
    optional chaining to preserve the original error that caused the failure.

    Args:
        message: Human-readable error message describing what went wrong
        original_error: The underlying exception that caused this error (optional)

    Example:
        try:
            api_client.initialize()
        except ValueError as e:
            raise APIInitializationError(
                f"Invalid API configuration: {e}",
                original_error=e
            ) from e
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class APIInitializationError(GoogleGenMediaException):
    """Raised when an API client fails to initialize.

    This typically indicates problems with:
    - Invalid or missing credentials
    - Invalid project ID or region
    - Network connectivity to Google Cloud
    - Missing required dependencies

    Example:
        raise APIInitializationError(
            "Failed to initialize GenAI client: invalid project ID 'test123'"
        )
    """

    pass


class APICallError(GoogleGenMediaException):
    """Raised when an API call fails during execution.

    This covers runtime failures such as:
    - Rate limiting / quota exhausted
    - Service unavailability / timeouts
    - Permission denied errors
    - Invalid request parameters
    - Network errors

    Example:
        raise APICallError(
            "Image generation failed: rate limit exceeded",
            original_error=api_exception
        )
    """

    pass


class ConfigurationError(GoogleGenMediaException):
    """Raised for configuration-related errors.

    This indicates invalid or incompatible parameter combinations:
    - Out of range numeric values
    - Invalid enum choices
    - Missing required parameters
    - Conflicting settings

    Example:
        raise ConfigurationError(
            "temperature must be between 0.0 and 1.0, got 1.5"
        )
    """

    pass


class FileProcessingError(GoogleGenMediaException):
    """Raised for errors during file processing.

    This covers file-related operations:
    - File not found
    - Unsupported file formats
    - Corrupted or invalid file data
    - File I/O errors
    - Base64 encoding/decoding failures

    Example:
        raise FileProcessingError(
            f"Failed to read image file '{path}': file not found"
        )
    """

    pass
