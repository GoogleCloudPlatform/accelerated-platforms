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
            retries = max_retries

            while True:
                try:
                    return func(*args, **kwargs)
                except (
                    api_core_exceptions.ResourceExhausted,
                    api_core_exceptions.ServiceUnavailable,
                    genai_errors.ServerError,
                ) as e:
                    if retries == 0:
                        raise exceptions.APICallError(
                            f"API call failed after {max_retries} retries: {e}"
                        ) from e

                    print(
                        f"API call failed with a retryable error: {e}. Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                    delay *= backoff
                    retries -= 1
                except (api_core_exceptions.InvalidArgument,) as e:
                    raise exceptions.ConfigurationError(
                        f"Invalid argument or configuration: {e}"
                    ) from e
                except (api_core_exceptions.PermissionDenied,) as e:
                    raise exceptions.APICallError(
                        f"Permission denied. Check your credentials and permissions. Error: {e}"
                    ) from e
                except (api_core_exceptions.DeadlineExceeded,) as e:
                    raise exceptions.APICallError(f"API request timed out: {e}") from e
                except (api_core_exceptions.GoogleAPICallError,) as e:
                    raise exceptions.APICallError(
                        f"An unexpected API error occurred: {e}"
                    ) from e

        return wrapper

    return decorator
