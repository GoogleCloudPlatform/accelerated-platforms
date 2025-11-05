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

from typing import Optional

from google import genai
from .config import get_gcp_metadata
from .custom_exceptions import ConfigurationError


class GoogleCloudClientBase:
    """
    A base class that *only* handles discovering the GCP project and region.
    """

    def __init__(
        self,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ):
        """
        Initializes the base client, discovering project and region.
        """
        self.project_id = gcp_project_id or get_gcp_metadata("project/project-id")
        self.region = gcp_region or "-".join(
            get_gcp_metadata("instance/zone").split("/")[-1].split("-")[:-1]
        )

        if not self.project_id:
            raise ConfigurationError(
                "GCP Project is required and could not be determined."
            )
        if not self.region:
            raise ConfigurationError(
                "GCP region is required and could not be determined."
            )

        print(
            f"[GoogleCloudClientBase] Project: {self.project_id}, Region: {self.region}"
        )


class VertexAIClient(GoogleCloudClientBase):  # Now inherits from the new base
    """
    A base class for initializing Vertex AI *Generative AI* (genai) clients.
    """

    def __init__(
        self,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initializes the Vertex AI genai.Client.
        """
        # Call the new base class to set self.project_id and self.region
        super().__init__(gcp_project_id=gcp_project_id, gcp_region=gcp_region)

        # Now, do the part specific to *this* client
        try:
            http_options = None
            if user_agent:
                http_options = genai.types.HttpOptions(
                    headers={"user-agent": user_agent}
                )

            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
                http_options=http_options,
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to initialize genai.Client for Vertex AI: {e}"
            )
