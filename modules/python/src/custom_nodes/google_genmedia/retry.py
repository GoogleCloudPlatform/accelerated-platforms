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
from grpc import StatusCode

from .custom_exceptions import APIExecutionError, APIInputError


def api_error_retry(func):
    """
    Decorator factory that implements centralized API error handling, retry logic,
    and exception mapping for functions interacting with the Google GenAI/Vertex AI API.

    The decorated function must accept 'model', 'retry_count', and 'retry_delay'
    as keyword arguments, or have them accessible via kwargs passed to the wrapper.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retry_count = kwargs.get("retry_count", 0)
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
                status_code = getattr(e, "code", None)
                details = getattr(e, "details", str(e))

                if status_code is None:
                    # If no status code, it's a generic unexpected error
                    raise APIExecutionError(
                        f"An unexpected API error occurred: {details}"
                    ) from e

                # Handle retryable errors (RESOURCE_EXHAUSTED and UNAVAILABLE)
                if status_code in (
                    StatusCode.RESOURCE_EXHAUSTED,
                    StatusCode.UNAVAILABLE,
                ):
                    if retries < retry_count:
                        retry_wait = retry_delay
                        error_type = (
                            "Quota/Resource Exhausted"
                            if status_code == StatusCode.RESOURCE_EXHAUSTED
                            else "Service Unavailable"
                        )
                        print(
                            f"API {error_type} (attempt {retries+1}/{retry_count}) - "
                            f"Code: {status_code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {details}"
                        )
                        time.sleep(retry_wait)
                        retries += 1  # Increment retry attempt counter
                        continue  # Go back to the top of the while loop
                    else:
                        error_type = (
                            "Quota/Resource Exhausted"
                            if status_code == StatusCode.RESOURCE_EXHAUSTED
                            else "Service Unavailable"
                        )
                        raise APIExecutionError(
                            f"API {error_type} after {retry_count} attempts for {model} (Code: {status_code.name}). Last error: {details}"
                        ) from e

                # Handle fatal non-retryable errors
                if status_code == StatusCode.INVALID_ARGUMENT:
                    raise APIInputError(
                        f"Invalid API argument supplied. Check your prompt and parameters. Error: {details}"
                    ) from e
                elif status_code in (
                    StatusCode.PERMISSION_DENIED,
                    StatusCode.UNAUTHENTICATED,
                    StatusCode.FORBIDDEN,
                ):
                    raise APIExecutionError(
                        f"Permission denied. Check your GCP service account permissions for API. Error: {details}"
                    ) from e
                elif status_code == StatusCode.DEADLINE_EXCEEDED:
                    raise APIExecutionError(
                        f"API request timed out (Deadline Exceeded). Error: {details}"
                    ) from e
                else:
                    # Catch any other unexpected Client/Server Error
                    raise APIExecutionError(
                        f"Unexpected API Error (Code: {status_code.name}). Error: {details}"
                    ) from e

            except Exception as e:
                # Catch any other unexpected non-API specific errors.
                raise APIExecutionError(
                    f"An unexpected non-API error occurred during API execution: {e}"
                ) from e

        # Should only be reached if the while loop somehow finished without returning or raising.
        raise APIExecutionError(
            f"API generation failed with an unknown error path after {retry_count+1} attempts."
        )

    return wrapper
