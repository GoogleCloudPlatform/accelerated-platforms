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

import functools
import time

from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors

from .custom_exceptions import APIExecutionError, APIInputError
from .logger import get_node_logger

logger = get_node_logger(__name__)


def api_error_retry(func):
    """
    Decorator factory that implements centralized API error handling, retry logic,
    and exception mapping for functions interacting with the Google GenAI/Vertex AI API.

    The decorated function must accept 'model', 'retry_count', and 'retry_delay'
    as keyword arguments, or have them accessible via kwargs passed to the wrapper.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retry_count = kwargs.get("retry_count", 3)
        retry_delay = kwargs.get("retry_delay", 5)
        model = kwargs.get(
            "model", "unknown_model"
        )  # Default model name for logging/error messages

        retries = 0
        while retries <= retry_count:
            try:
                # Execute the wrapped function (which contains the single API call)
                return func(*args, **kwargs)

            except (
                genai_errors.ClientError,
                genai_errors.ServerError,
                api_core_exceptions.GoogleAPICallError,
            ) as e:
                # Standardize error handling to gRPC status codes
                status_code = e.code
                details = e.message

                if status_code is None:
                    # If no status code, it's a generic unexpected error
                    raise APIExecutionError(
                        f"An unexpected API error occurred: {details}"
                    ) from e

                # Handle retryable errors (RESOURCE_EXHAUSTED and UNAVAILABLE)
                if status_code in (429, 503):
                    if retries < retry_count:
                        retry_wait = retry_delay
                        error_type = (
                            "Quota/Resource Exhausted"
                            if status_code == 429
                            else "Service Unavailable"
                        )
                        logger.warning(
                            f"API {error_type} (attempt {retries+1}/{retry_count}) - "
                            f"Code: {status_code}. Waiting {retry_wait:.1f} seconds before retry. Error: {details}"
                        )
                        time.sleep(retry_wait)
                        retries += 1  # Increment retry attempt counter
                        continue  # Go back to the top of the while loop
                    else:
                        error_type = (
                            "Quota/Resource Exhausted"
                            if status_code == 429
                            else "Service Unavailable"
                        )
                        raise APIExecutionError(
                            f"API {error_type} after {retry_count} attempts for {model} (Code: {status_code}). Last error: {details}"
                        ) from e

                # Handle fatal non-retryable errors
                if status_code == 400:
                    raise APIInputError(details) from e
                elif status_code == 404:
                    raise APIExecutionError(
                        f"Unable to find the requested resource; please confirm that your project ID and region are valid."
                    ) from e
                elif status_code in (403, 401):
                    raise APIExecutionError(
                        f"The project ID either doesn't exist or you don't have permissions to access it."
                    ) from e
                elif status_code == 504:
                    raise APIExecutionError(details) from e
                else:
                    raise APIExecutionError(details) from e

            except Exception as e:
                # Catch any other unexpected non-API specific errors.
                raise APIExecutionError(
                    f"An unexpected non-API error occurred: {e}"
                ) from e

        # Should only be reached if the while loop somehow finished without returning or raising.
        raise APIExecutionError(
            f"API generation failed with an unknown error path after {retry_count+1} attempts."
        )

    return wrapper
