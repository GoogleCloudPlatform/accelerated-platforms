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

"""A retry decorator for handling transient API errors."""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors

from . import exceptions

# Set up logging
logger = logging.getLogger(__name__)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


def _extract_error_message(error: Exception) -> str:
    """Extract a formatted error message from an exception.

    Args:
        error: The exception to extract message from

    Returns:
        Formatted error message string
    """
    code = getattr(error, "code", "N/A")
    status = getattr(error, "status", "N/A")
    message = getattr(error, "message", str(error))
    return f"code: {code} status: {status} message: {message}"


def retry_on_api_error(
    initial_delay: float = 5,
    max_retries: int = 3,
    backoff: float = 2,
):
    """
    A decorator to retry a function on transient errors and translate
    permanent errors into custom exceptions.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                # --- NON-RETRYABLE ERRORS (Fail Immediately) ---

                except genai_errors.ClientError as e:
                    # Check if the specific error code is 404 Not Found.
                    if e.code == 404:
                        message = f"{e.code} - ({e.status}): Please check your project id and region"
                    else:
                        # Handle all other client errors (e.g., 400, 401, 403, 429).
                        message = f"{e.code} - ({e.status}): {e.message}"

                    raise exceptions.ConfigurationError(message) from e

                # --- RETRYABLE ERRORS (Wait and try again) ---

                except (
                    api_core_exceptions.ServiceUnavailable,
                    genai_errors.ServerError,
                ) as e:
                    last_exception = e
                    message = f"A temporary, retryable error occurred: {e.message}"
                    print(
                        f"{message}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= backoff

            # If the loop completes, all retries for a server error have failed.
            raise exceptions.APICallError(
                f"API call failed after {max_retries} retries: {last_exception.message}"
            ) from last_exception

        return wrapper

    return decorator
