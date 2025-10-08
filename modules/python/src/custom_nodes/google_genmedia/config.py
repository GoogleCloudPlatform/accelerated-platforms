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
from functools import lru_cache
from typing import Optional

import requests
from google import genai
from google.api_core import exceptions as api_core_exceptions
from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import aiplatform
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from . import exceptions
from .constants import (
    PROJECT_ID_MAX_LENGTH,
    PROJECT_ID_MIN_LENGTH,
    PROJECT_ID_PATTERN,
    PROJECT_ID_RESTRICTED_STRINGS,
    REGION_PATTERN,
    SPECIAL_REGIONS,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def get_gcp_metadata(path: str) -> Optional[str]:
    """
    Fetches instance metadata from the GCP metadata server with caching.

    Args:
        path: The metadata path to fetch (e.g., 'project/project-id')

    Returns:
        The metadata value as a string, or None if unavailable
    """
    headers = {"Metadata-Flavor": "Google"}
    url = f"http://metadata.google.internal/computeMetadata/v1/{path}"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except (HTTPError, Timeout, ConnectionError) as e:
        logger.debug("Could not fetch GCP metadata from %s: %s", url, e)
        return None
    except RequestException as e:
        logger.warning(
            "Unexpected network error fetching GCP metadata from %s: %s", url, e
        )
        return None


class GoogleGenAIBaseAPI:
    """
    Base class for Google GenAI API clients that handles initialization logic.

    This class handles:
    - Project ID and region discovery and validation
    - Client initialization for both GenAI and Prediction clients
    - Proper error handling and reporting
    """

    def __init__(
        self,
        user_agent: str,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        client_type: str = "genai",
    ):
        """
        Initializes the client.

        Args:
            user_agent: User agent string for API requests.
            project_id: GCP Project ID. If not provided, will attempt to discover from environment.
            region: GCP region. If not provided, will attempt to discover from environment.
            client_type: Type of client to initialize ('genai' or 'prediction').

        Raises:
            exceptions.APIInitializationError: If initialization fails or required parameters cannot be determined.
            exceptions.ConfigurationError: If provided parameters are invalid.
        """
        self.user_agent = user_agent

        # --- Project ID Handling ---
        if project_id:
            self._validate_project_id(project_id)
            self.project_id = project_id
        else:
            self.project_id = self._discover_project_id()

        if not self.project_id:
            raise exceptions.APIInitializationError(
                "GCP Project ID is required but could not be determined automatically. "
                "Please provide a project_id or ensure you're running on GCP with metadata server access."
            )

        # --- Region Handling ---
        if region:
            self._validate_region(region)
            self.region = region
        else:
            self.region = self._discover_region()

        if not self.region:
            raise exceptions.APIInitializationError(
                "GCP region is required but could not be determined automatically. "
                "Please provide a region or ensure you're running on a GCP instance."
            )

        # --- Client Initialization ---
        self.client = None
        if client_type == "genai":
            self._initialize_genai_client()
        elif client_type == "prediction":
            self._initialize_prediction_client()
        else:
            raise exceptions.ConfigurationError(
                f"Invalid client_type: '{client_type}'. Must be 'genai' or 'prediction'."
            )

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        """Validates a GCP project ID."""
        if not project_id:
            raise exceptions.ConfigurationError("Project ID cannot be empty")

        if not (PROJECT_ID_MIN_LENGTH <= len(project_id) <= PROJECT_ID_MAX_LENGTH):
            raise exceptions.ConfigurationError(
                f"Invalid Project ID '{project_id}': Must be {PROJECT_ID_MIN_LENGTH} to {PROJECT_ID_MAX_LENGTH} characters."
            )

        if not PROJECT_ID_PATTERN.match(project_id):
            raise exceptions.ConfigurationError(
                f"Invalid Project ID '{project_id}': Must start with a lowercase letter, "
                "contain only lowercase letters, numbers, and hyphens, and not end with a hyphen."
            )

        for restricted in PROJECT_ID_RESTRICTED_STRINGS:
            if restricted in project_id.lower():
                raise exceptions.ConfigurationError(
                    f"Invalid Project ID '{project_id}': Cannot contain restricted string '{restricted}'"
                )

    @staticmethod
    def _validate_region(region: str) -> None:
        """Validates a GCP region format."""
        if not region:
            raise exceptions.ConfigurationError("Region cannot be empty")

        if region in SPECIAL_REGIONS:
            return

        if not REGION_PATTERN.match(region):
            raise exceptions.ConfigurationError(
                f"Invalid region format: '{region}'. Expected format like 'us-central1' or 'global'"
            )

    def _initialize_genai_client(self) -> None:
        """Initializes the GenAI client."""
        logger.info(
            "Initializing GenAI client for project '%s' in region '%s'",
            self.project_id,
            self.region,
        )
        http_options = genai.types.HttpOptions(headers={"user-agent": self.user_agent})
        try:
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
                http_options=http_options,
            )
        except api_core_exceptions.NotFound as e:
            raise exceptions.APIInitializationError(
                f"Invalid project or region. The combination of project '{self.project_id}' "
                f"and region '{self.region}' was not found."
            ) from e
        except api_core_exceptions.PermissionDenied as e:
            raise exceptions.APIInitializationError(
                f"Permission denied for project '{self.project_id}'. Please check your API key and permissions."
            ) from e
        except api_core_exceptions.ClientError as e:
            raise exceptions.APIInitializationError(
                f"A client-side error occurred during initialization: {e.message}"
            ) from e
        except Exception as e:
            raise exceptions.APIInitializationError(
                f"An unexpected error occurred during client initialization for project '{self.project_id}'."
            ) from e

    def _initialize_prediction_client(self) -> None:
        """Initializes the Vertex AI Prediction client."""
        logger.info(
            "Initializing Prediction client for project '%s' in region '%s'",
            self.project_id,
            self.region,
        )
        try:
            aiplatform.init(project=self.project_id, location=self.region)
            api_regional_endpoint = f"{self.region}-aiplatform.googleapis.com"
            client_options = {"api_endpoint": api_regional_endpoint}
            client_info = ClientInfo(user_agent=self.user_agent)
            self.client = aiplatform.gapic.PredictionServiceClient(
                client_options=client_options, client_info=client_info
            )
        except api_core_exceptions.NotFound as e:
            message = self._format_api_error(e)
            raise exceptions.APIInitializationError(
                f"Invalid region '{self.region}' for project '{self.project_id}'. "
                f"Please check the region and try again. Full error: {message}"
            ) from e
        except Exception as e:
            message = self._format_api_error(e)
            raise exceptions.APIInitializationError(
                f"Failed to initialize Prediction client for project '{self.project_id}' "
                f"in region '{self.region}'. Full error: {message}"
            ) from e

    @staticmethod
    def _format_api_error(e: Exception) -> str:
        """
        Creates a consistent, readable error message from an API exception.
        """
        code = getattr(e, "code", None)
        message = getattr(e, "message", str(e))
        return f"[{code}] {message}" if code else message

    @staticmethod
    def _discover_project_id() -> Optional[str]:
        """
        Discovers the project ID from the GCP metadata server.
        """
        project_id = get_gcp_metadata("project/project-id")
        if project_id:
            logger.debug("Discovered project ID from metadata: %s", project_id)
        else:
            logger.debug("Could not discover project ID from metadata server")
        return project_id

    @staticmethod
    def _discover_region() -> Optional[str]:
        """
        Discovers the region from the instance's zone.
        """
        zone = get_gcp_metadata("instance/zone")
        if not zone:
            return None
        return "-".join(zone.split("/")[-1].split("-")[:-1])
