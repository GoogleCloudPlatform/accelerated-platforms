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
from typing import Optional

import requests
from google import genai
from google.api_core import exceptions as api_core_exceptions
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from . import exceptions


class GoogleGenAIBaseAPI:
    """Base class for Google GenAI API clients."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initializes the API client.

        Args:
            project_id: The GCP project ID.
            region: The GCP region.
            user_agent: The user agent to use for the API client.

        Raises:
            exceptions.APIInitializationError: If the API client cannot be initialized.
        """
        self.project_id = project_id or get_gcp_metadata("project/project-id")
        self.region = region
        if not self.region:
            zone = get_gcp_metadata("instance/zone")
            if zone:
                self.region = "-".join(zone.split("/")[-1].split("-")[:-1])

        if not self.project_id:
            raise exceptions.APIInitializationError("GCP Project is required")
        if not self.region:
            raise exceptions.APIInitializationError("GCP region is required")

        print(f"Project is {self.project_id}, region is {self.region}")

        http_options = None
        if user_agent:
            http_options = genai.types.HttpOptions(headers={"user-agent": user_agent})

        try:
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
                http_options=http_options,
            )
        except api_core_exceptions.InvalidArgument as e:
            message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
            print(f"Error initializing client with region {self.region}: {message}")
            raise exceptions.APIInitializationError(
                f"Failed to initialize client, your region {self.region} might be wrong. Please pass `global` if you are not sure. Full error: {message}"
            ) from e
        except Exception as e:
            message = f"code: {getattr(e, 'code', 'N/A')} status: {getattr(e, 'status', 'N/A')} message: {getattr(e, 'message', e)}"
            print(f"Failed to initialize genai.Client for Vertex AI: {message}")
            raise exceptions.APIInitializationError(
                f"Failed to initialize genai.Client for Vertex AI: {message}"
            ) from e


# Fetch GCP project ID and zone required to authenticate with Vertex AI APIs
def get_gcp_metadata(path):
    headers = {"Metadata-Flavor": "Google"}
    try:
        response = requests.get(
            f"http://metadata.google.internal/computeMetadata/v1/{path}",
            headers=headers,
            timeout=5,
        )
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.text.strip()
    except (HTTPError, Timeout, ConnectionError) as e:
        print(f"Error fetching metadata from {path} due to network issue: {e}")
        return None
    except RequestException as e:
        print(f"An unexpected error occurred while fetching metadata from {path}: {e}")
        return None
