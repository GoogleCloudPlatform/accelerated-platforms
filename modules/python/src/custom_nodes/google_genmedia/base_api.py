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

"""Base class for Google GenAI API clients."""

from typing import Optional

from google import genai

from . import exceptions
from .config import get_gcp_metadata


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
        except Exception as e:
            raise exceptions.APIInitializationError(
                f"Failed to initialize genai.Client for Vertex AI: {e}"
            ) from e
