# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module provides a base class for initializing Google GenAI clients.
"""

import logging
import re
from typing import Optional

import requests
from google import genai
from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import aiplatform
from google.cloud import compute_v1
from google.api_core import exceptions as google_exceptions
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

# Assuming a local exceptions file
from . import exceptions

# --- Module Level Constants ---
METADATA_URL_BASE = "http://metadata.google.internal/computeMetadata/v1/"
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 30

logger = logging.getLogger(__name__)

project_id_requirements = """
A project ID has the following requirements:
- Must be 6 to 30 characters in length.
- Can only contain lowercase letters, numbers, and hyphens.
- Must start with a letter.
- Cannot end with a hyphen.
- Cannot be in use or previously used; this includes deleted projects.
- Cannot contain restricted strings such as 'google' and 'ssl'.
"""


def get_gcp_metadata(path: str) -> Optional[str]:
    """Fetches instance metadata from the GCP metadata server."""
    headers = {"Metadata-Flavor": "Google"}
    try:
        response = requests.get(
            f"{METADATA_URL_BASE}{path}",
            headers=headers,
            timeout=_DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.text.strip()
    except (HTTPError, Timeout, ConnectionError):
        return None
    except RequestException as e:
        logger.warning("Unexpected network error fetching GCP metadata: %s", e)
        return None


class GoogleGenAIBaseAPI:
    """
    Base class for Google GenAI API clients that handles initialization logic.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_type: str = "genai",
    ):
        """
        Initializes the client.

        For both project_id and region:
        - If a value is provided, it is validated.
        - If a value is not provided, it is discovered from the environment.
        """
        # --- Project ID Handling ---
        if project_id:
            self._validate_project_id(project_id)
            self.project_id = project_id
        else:
            self.project_id = self._discover_project_id()

        if not self.project_id:
            raise exceptions.APIInitializationError(
                "GCP Project ID is required and could not be determined automatically."
            )

        # --- Region Handling ---
        if region:
            self._validate_region(region)
            self.region = region
        else:
            self.region = self._discover_region()

        if not self.region:
            raise exceptions.APIInitializationError(
                "GCP region is required and could not be determined automatically."
            )

        # --- Client Initialization ---
        if client_type == "genai":
            logger.info(
                "Initializing GenAI client for project '%s' in region '%s'",
                self.project_id,
                self.region,
            )
            http_options = (
                genai.types.HttpOptions(headers={"user-agent": user_agent})
                if user_agent
                else None
            )
            try:
                self.client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.region,
                    http_options=http_options,
                )
            except Exception as e:
                message = self._format_api_error(e)
                raise exceptions.APIInitializationError(
                    f"Failed to initialize client for project '{self.project_id}' "
                    f"in region '{self.region}'. The region may be invalid. Full error: {message}"
                ) from e
        elif client_type == "prediction":
            logger.info(
                "Initializing Prediction client for project '%s' in region '%s'",
                self.project_id,
                self.region,
            )
            try:
                aiplatform.init(project=self.project_id, location=self.region)
                self.api_regional_endpoint = f"{self.region}-aiplatform.googleapis.com"
                self.client_options = {"api_endpoint": self.api_regional_endpoint}
                self.client_info = ClientInfo(user_agent=user_agent)
                self.client = aiplatform.gapic.PredictionServiceClient(
                    client_options=self.client_options, client_info=self.client_info
                )
            except Exception as e:
                message = self._format_api_error(e)
                raise exceptions.APIInitializationError(
                    f"Failed to initialize Prediction client for project '{self.project_id}' "
                    f"in region '{self.region}'. Full error: {message}"
                ) from e
        else:
            raise ValueError(f"Invalid client_type: {client_type}")

    @staticmethod
    def _format_api_error(e: Exception) -> str:
        """Creates a consistent, readable error message from an API exception."""
        code = getattr(e, "code", "N/A")
        message = getattr(e, "message", str(e))
        return f"Code: {code}, Message: {message}"

    @staticmethod
    def _discover_project_id() -> Optional[str]:
        """Discovers the project ID from the GCP metadata server."""
        return get_gcp_metadata("project/project-id")

    @staticmethod
    def _discover_region() -> Optional[str]:
        """Discovers the region from the instance's zone."""
        zone = get_gcp_metadata("instance/zone")
        return "-".join(zone.split("/")[-1].split("-")[:-1])

    @staticmethod
    def _validate_project_id(project_id: str):
        """Performs validation of the GCP project ID format."""
        if not 6 <= len(project_id) <= 30:
            raise exceptions.APIInitializationError(
                f"Invalid Project ID '{project_id}': Must be 6 to 30 characters."
            )
        if not re.match(r"^[a-z]([a-z0-9-]{4,28}[a-z0-9])?$", project_id):
            raise exceptions.APIInitializationError(
                f"Invalid Project ID '{project_id}': Does not meet GCP format requirements."
                f"{project_id_requirements}"
            )

    def _validate_region(self, region: str):
        """Performs format and dynamic validation for the GCP region string."""
        if not re.match(r"^[a-z]+-[a-z]+[0-9]+$", region):
            raise exceptions.APIInitializationError(
                f"Invalid region format: '{region}'. Expected format like 'us-central1."
            )
        try:
            regions_client = compute_v1.RegionsClient()
            request = compute_v1.ListRegionsRequest(project=self.project_id)
            available_regions = {r.name for r in regions_client.list(request=request)}

            if region not in available_regions:
                raise exceptions.APIInitializationError(
                    f"Region '{region}' is not a valid or available GCP region for project '{self.project_id}'."
                )
        except google_exceptions.NotFound:
            raise exceptions.APIInitializationError(
                f"Could not verify region '{region}'."
            )
        except google_exceptions.PermissionDenied:
            raise exceptions.APIInitializationError(
                f"Could not verify region '{region}'. Permission denied to access resources for project "
                f"'{self.project_id}'. Please check your authentication credentials."
            )
        except Exception as e:
            raise exceptions.APIInitializationError(
                f"An unexpected error occurred while validating region '{region}': {e}"
            ) from e
