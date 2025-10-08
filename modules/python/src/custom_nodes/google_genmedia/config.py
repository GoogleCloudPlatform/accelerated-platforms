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
from functools import lru_cache
from typing import Optional

import requests
from google import genai
from google.genai import errors as genai_errors
from google.api_core.gapic_v1.client_info import ClientInfo
from google.api_core import exceptions as core_exceptions
from google.cloud import aiplatform
from google.api_core import exceptions as api_core_exceptions
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from . import exceptions

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
    url = f"{METADATA_URL_BASE}{path}"

    try:
        response = requests.get(
            f"http://metadata.google.internal/computeMetadata/v1/{path}",
            headers=headers,
            timeout=30,
        )
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


class GCPProjectValidator:
    """Validates GCP project IDs according to Google Cloud requirements."""

    PROJECT_ID_PATTERN = re.compile(r"^[a-z]([a-z0-9-]{4,28}[a-z0-9])?$")
    MIN_LENGTH = 6
    MAX_LENGTH = 30

    RESTRICTED_STRINGS = {"google", "ssl", "www", "goog"}

    @classmethod
    def validate(cls, project_id: str) -> None:
        """
        Validates a GCP project ID.

        Args:
            project_id: The project ID to validate

        Raises:
            exceptions.ConfigurationError: If the project ID is invalid
        """
        if not project_id:
            raise exceptions.ConfigurationError("Project ID cannot be empty")

        # Length check
        if not cls.MIN_LENGTH <= len(project_id) <= cls.MAX_LENGTH:
            raise exceptions.ConfigurationError(
                f"Invalid Project ID '{project_id}': Must be {cls.MIN_LENGTH} to {cls.MAX_LENGTH} characters. "
                f"Current length: {len(project_id)}"
            )

        # Format check
        if not cls.PROJECT_ID_PATTERN.match(project_id):
            raise exceptions.ConfigurationError(
                f"Invalid Project ID '{project_id}': Must start with a lowercase letter, "
                "contain only lowercase letters, numbers, and hyphens, "
                "and cannot end with a hyphen."
            )

        # Check for restricted strings
        project_id_lower = project_id.lower()
        for restricted in cls.RESTRICTED_STRINGS:
            if restricted in project_id_lower:
                raise exceptions.ConfigurationError(
                    f"Invalid Project ID '{project_id}': Cannot contain restricted string '{restricted}'"
                )


class GCPRegionValidator:
    """Validates GCP regions."""

    REGION_PATTERN = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")
    SPECIAL_REGIONS = {"global", "us", "eu", "asia"}

    @classmethod
    def validate(cls, region: str) -> None:
        """
        Validates a GCP region format.

        Args:
            region: The region to validate

        Raises:
            exceptions.ConfigurationError: If the region format is invalid
        """
        if not region:
            raise exceptions.ConfigurationError("Region cannot be empty")

        # Allow special regions
        if region in cls.SPECIAL_REGIONS:
            return

        # Validate format (e.g., 'us-central1')
        if not cls.REGION_PATTERN.match(region):
            raise exceptions.ConfigurationError(
                f"Invalid region format: '{region}'. "
                "Expected format like 'us-central1', 'europe-west1', or 'global'"
            )

        logger.debug(
            "Region '%s' has valid format. Actual availability will be verified by API.",
            region,
        )


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
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_type: str = "genai",
    ):
        """
        Initializes the client.

        Args:
            project_id: GCP Project ID. If not provided, will attempt to discover from environment.
            region: GCP region. If not provided, will attempt to discover from environment.
            user_agent: Optional user agent string for API requests.
            client_type: Type of client to initialize ('genai' or 'prediction').

        Raises:
            exceptions.APIInitializationError: If initialization fails or required parameters cannot be determined.
            exceptions.ConfigurationError: If provided parameters are invalid.
        """
        self.user_agent = user_agent

        # --- Project ID Handling ---
        if project_id:
            GCPProjectValidator.validate(project_id)
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
            GCPRegionValidator.validate(region)
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

    def _initialize_genai_client(self) -> None:
        """Initializes the GenAI client."""
        logger.info(
            "Initializing GenAI client for project '%s' in region '%s'",
            self.project_id,
            self.region,
        )

        http_options = None
        if self.user_agent:
            http_options = genai.types.HttpOptions(
                headers={"user-agent": self.user_agent}
            )
            try:
                self.client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.region,
                    http_options=http_options,
                )
            except api_core_exceptions.NotFound as e:  # Specific block is now first
                raise exceptions.APIInitializationError(
                    f"Invalid project or region. The combination of project '{self.project_id}' "
                    f"and region '{self.region}' was not found."
                ) from e
            except api_core_exceptions.PermissionDenied as e:  # Another specific client error
                raise exceptions.APIInitializationError(
                    f"Permission denied for project '{self.project_id}'. Please check your API key and permissions."
                ) from e
            except api_core_exceptions.ClientError as e:  # General client error is the fallback
                raise exceptions.APIInitializationError(
                    f"A client-side error occurred during initialization: {e.message}"
                ) from e
            except Exception as e:  # Catch any other unexpected error
                raise exceptions.APIInitializationError(
                    f"An unexpected error occurred during client initialization for project '{self.project_id}'."
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
                self.client_info = ClientInfo(user_agent=self.user_agent)
                self.client = aiplatform.gapic.PredictionServiceClient(
                    client_options=self.client_options, client_info=self.client_info
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
        else:
            raise ValueError(f"Invalid client_type: {client_type}")

    @staticmethod
    def _format_api_error(e: Exception) -> str:
        """
        Creates a consistent, readable error message from an API exception.

        Args:
            e: The exception to format

        Returns:
            Formatted error message
        """
        code = getattr(e, "code", None)
        message = getattr(e, "message", str(e))

        if code:
            return f"[{code}] {message}"
        return message

    @staticmethod
    def _discover_project_id() -> Optional[str]:
        """
        Discovers the project ID from the GCP metadata server.

        Returns:
            Project ID if available, None otherwise
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

        Returns:
            Region if available, None otherwise
        """
        zone = get_gcp_metadata("instance/zone")
        if not zone:
            return None
        return "-".join(zone.split("/")[-1].split("-")[:-1])

    @staticmethod
    def _validate_project_id(project_id: str):
        """Performs validation of the GCP project ID format."""
        project_id_requirements = """
        A project ID has the following requirements:
        - Must be 6 to 30 characters in length.
        - Can only contain lowercase letters, numbers, and hyphens.
        - Must start with a letter.
        - Cannot end with a hyphen.
        - Cannot be in use or previously used; this includes deleted projects.
        - Cannot contain restricted strings such as 'google' and 'ssl'.
        """
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
        if region == "global":
            return
        if not re.match(r"^[a-z]+-[a-z]+[0-9]+$", region):
            raise exceptions.APIInitializationError(
                f"Invalid region format: '{region}'. Expected format like 'us-central1' or 'global'"
            )
