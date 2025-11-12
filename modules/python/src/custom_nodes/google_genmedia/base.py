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
from .logger import get_node_logger

logger = get_node_logger(__name__)


class VertexAIClient:
    """
    A base class for initializing Vertex AI clients.
    """

    def __init__(
        self,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Initializes the Vertex AI client.

        Args:
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.
            user_agent: The user agent string for the client.

        Raises:
            ConfigurationError: If GCP Project or region cannot be determined.
        """
        self.project_id = gcp_project_id or get_gcp_metadata("project/project-id")
        if gcp_region:
            self.region = gcp_region
        else:
            zone_metadata = get_gcp_metadata("instance/zone")
            if zone_metadata:
                try:
                    zone_name = zone_metadata.split("/")[-1]
                    self.region = "-".join(zone_name.split("-")[:-1])
                except Exception as e:
                    logger.error(
                        f"Failed to parse region from zone metadata '{zone_metadata}': {e}"
                    )
                    self.region = None
            else:
                self.region = None

        if not self.project_id:
            raise ConfigurationError(
                "GCP Project is required and could not be determined."
            )
        if not self.region:
            raise ConfigurationError(
                "GCP region is required and could not be determined."
            )

        logger.info(f"Project is {self.project_id}, region is {self.region}")

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
                raise ConfigurationError(
                    f"Failed to initialize genai.Client for Vertex AI: {e}"
                )
