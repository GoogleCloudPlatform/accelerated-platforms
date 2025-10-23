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

# This is a preview version of veo2 custom node
# Copyright 2025 Google LLC
# (license header)

from typing import Dict, List, Optional

from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import aiplatform

from . import utils
from .config import get_gcp_metadata
from .constants import LYRIA2_MODEL, LYRIA2_USER_AGENT
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .retry import api_error_retry


class Lyria2API:
    """
    A class to interact with the Imagen API for image generation.
    """

    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initializes the client.

        Args:
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.

        Raises:
            ConfigurationError: If GCP Project or region cannot be determined or client initialization fails.
        """
        self.project_id = project_id or get_gcp_metadata("project/project-id")
        self.region = region or "-".join(
            get_gcp_metadata("instance/zone").split("/")[-1].split("-")[:-1]
        )
        if not self.project_id:
            raise ConfigurationError("GCP Project is required")
        if not self.region:
            raise ConfigurationError("GCP region is required")

        print(f"Project is {self.project_id}, region is {self.region}")
        try:
            aiplatform.init(project=self.project_id, location=self.region)
            self.api_regional_endpoint = f"{self.region}-aiplatform.googleapis.com"
            self.client_options = {"api_endpoint": self.api_regional_endpoint}
            self.client_info = ClientInfo(user_agent=LYRIA2_USER_AGENT)
            self.client = aiplatform.gapic.PredictionServiceClient(
                client_options=self.client_options, client_info=self.client_info
            )
            self.model_endpoint = f"projects/{self.project_id}/locations/{self.region}/publishers/google/models/{LYRIA2_MODEL}"
            print(
                f"Prediction client initiated on project : {self.project_id}, location: {self.region}"
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to initialize Prediction client for Vertex AI: {e}"
            )

    @api_error_retry
    def generate_music_from_text(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        sample_count: int = 1,
        seed: int = 0,
    ) -> dict:
        """
        Generates music from a text prompt using the Lyria 2 API.
        Args:
            prompt: The text prompt for music generation.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            sample_count: The number of music samples to generate.
            seed: An optional seed for reproducible music generation.
        Returns:
            A list of file paths to the generated music.
        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If music generation fails due to API or unexpected issues.
        """
        instance = {"prompt": str(prompt)}
        if negative_prompt:
            instance["negative_prompt"] = str(negative_prompt)
        if seed > 0:
            instance["seed"] = seed
            instance["sample_count"] = 1
        else:
            instance["seed"] = 0
            instance["sample_count"] = sample_count
        print(f"Lyria Node: Instance: {instance}")
        response = self.client.predict(
            endpoint=self.model_endpoint, instances=[instance]
        )
        print(
            f"Lyria Node: Response received from model: {response.model_display_name}"
        )

        return utils.process_audio_response(response)
