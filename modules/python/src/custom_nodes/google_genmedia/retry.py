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

import requests
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
) -> Callable[[F], F]:
    """A decorator to retry a function call on specific transient API errors.

    This decorator will retry the wrapped function when it encounters specific
    transient errors (resource exhausted, service unavailable, server errors).
    It uses exponential backoff for retries.

    Non-retryable errors (invalid arguments, permission denied, timeouts) are
    immediately raised as appropriate custom exceptions.

    Args:
        initial_delay: Initial delay in seconds before first retry (default: 5)
        max_retries: Maximum number of retry attempts (default: 3)
        backoff: Multiplier for exponential backoff (default: 2)

    Returns:
        Decorated function that will retry on transient errors
    """
    # Define which exceptions should trigger retries
    RETRYABLE_EXCEPTIONS = (
        api_core_exceptions.ResourceExhausted,
        api_core_exceptions.ServiceUnavailable,
        genai_errors.ServerError,
    )

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    error_msg = _extract_error_message(e)
                    logger.warning(
                        f"Retryable API error (attempt {attempt + 1}/{max_retries}): {error_msg}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    if attempt < max_retries - 1:  # Don't sleep after last attempt
                        time.sleep(delay)
                        delay *= backoff

                except api_core_exceptions.InvalidArgument as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"Invalid argument or configuration: {error_msg}")
                    raise exceptions.ConfigurationError(
                        f"Invalid argument or configuration: {error_msg}"
                    ) from e

                except api_core_exceptions.PermissionDenied as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"Permission denied: {error_msg}")
                    raise exceptions.APICallError(
                        f"Permission denied. Check your credentials and permissions. Error: {error_msg}"
                    ) from e

                except api_core_exceptions.DeadlineExceeded as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"API request timed out: {error_msg}")
                    raise exceptions.APICallError(
                        f"API request timed out: {error_msg}"
                    ) from e

                except api_core_exceptions.NotFound as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"API endpoint not found: {error_msg}")
                    raise exceptions.ConfigurationError(
                        "The provided region may be invalid or the API may not be available in that region."
                    ) from e

                except api_core_exceptions.GoogleAPICallError as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"Unexpected API error: {error_msg}")
                    raise exceptions.APICallError(
                        f"An unexpected API error occurred: {error_msg}"
                    ) from e

                except requests.exceptions.RequestException as e:
                    error_msg = _extract_error_message(e)
                    logger.error(f"Network request failed: {error_msg}")
                    raise exceptions.APICallError(
                        f"Network request failed: {error_msg}"
                    ) from e

            # If all retries exhausted
            error_msg = _extract_error_message(last_exception)
            logger.error(
                f"API call failed after {max_retries} retries. Last error: {error_msg}"
            )
            raise exceptions.APICallError(
                f"API call failed after {max_retries} retries: {error_msg}"
            ) from last_exception

        return wrapper

    return decorator
