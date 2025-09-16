# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.f
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Custom exceptions for Google GenMedia custom nodes."""

import re


class GoogleGenMediaException(Exception):
    """Base exception for the Google GenMedia custom nodes."""

    def __init__(self, *args):
        # This logic is to extract a clean error message from the
        # exceptions raised by the Google GenAI API.
        full_error_str = " ".join(str(a) for a in args)
        match = re.search(r"'message': '(.*?)', 'status'", full_error_str)
        if match:
            message = match.group(1)
        else:
            message_parts = []
            for arg in args:
                arg_str = str(arg)
                dict_start = arg_str.find("{'error':")
                if dict_start != -1:
                    arg_str = arg_str[:dict_start].strip()
                message_parts.append(arg_str)
            message = " ".join(message_parts)
        super().__init__(message)


class APIInitializationError(GoogleGenMediaException):
    """Raised when an API client fails to initialize."""

    def __init__(self, *args):
        super().__init__(*args)


class APICallError(GoogleGenMediaException):
    """Raised when an API call fails."""

    def __init__(self, *args):
        super().__init__(*args)


class ConfigurationError(GoogleGenMediaException):
    """Raised for configuration-related errors."""

    def __init__(self, *args):
        super().__init__(*args)


class FileProcessingError(GoogleGenMediaException):
    """Raised for errors during file processing."""

    def __init__(self, *args):
        super().__init__(*args)
