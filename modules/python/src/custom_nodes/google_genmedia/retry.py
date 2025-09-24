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
import time

import requests
from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors

from . import exceptions


def retry_on_api_error(
    initial_delay: float = 5,
    max_retries: int = 3,
    backoff: float = 2,
):
    """A decorator to retry a function call on specific API errors."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (
                    api_core_exceptions.ResourceExhausted,
                    api_core_exceptions.ServiceUnavailable,
                    genai_errors.ServerError,
                ) as e:
                    last_exception = e
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(f"A retryable error occurred: {message}")
                    print(
                        f"API call failed with a retryable error: {message}. Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= backoff
                except (api_core_exceptions.InvalidArgument,) as e:
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(f"Invalid argument or configuration: {message}")
                    raise exceptions.ConfigurationError(
                        f"Invalid argument or configuration: {message}"
                    ) from e
                except (api_core_exceptions.PermissionDenied,) as e:
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(
                        f"Permission denied. Check your credentials and permissions. Error: {message}"
                    )
                    raise exceptions.APICallError(
                        f"Permission denied. Check your credentials and permissions. Error: {message}"
                    ) from e
                except (api_core_exceptions.DeadlineExceeded,) as e:
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(f"API request timed out: {message}")
                    raise exceptions.APICallError(f"API request timed out: {message}") from e
                except (api_core_exceptions.GoogleAPICallError,) as e:
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(f"An unexpected API error occurred: {message}")
                    raise exceptions.APICallError(
                        f"An unexpected API error occurred: {message}"
                    ) from e
                except requests.exceptions.RequestException as e:
                    message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
                    print(f"Network request failed: {message}")
                    raise exceptions.APICallError(f"Network request failed: {message}") from e

            # If the loop completes, all retries have failed.
            raise exceptions.APICallError(
                f"API call failed after {max_retries} retries: {last_exception}"
            ) from last_exception

        return wrapper

    return decorator
