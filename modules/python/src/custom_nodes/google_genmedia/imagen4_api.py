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

from typing import List, Optional

from google import genai
from PIL import Image

from . import utils
from .base import VertexAIClient
from .constants import IMAGEN4_USER_AGENT, Imagen4Model
from .custom_exceptions import APIInputError, ConfigurationError


class Imagen4API(VertexAIClient):
    """
    A class to interact with the Imagen API for image generation.
    """

    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initializes the Imagen4API client.

        Args:
            project_id: The GCP project ID. If None, it will be retrieved from GCP metadata.
            region: The GCP region. If None, it will be retrieved from GCP metadata.

        Raises:
            ConfigurationError: If GCP Project or region cannot be determined or client initialization fails.
        """
        super().__init__(
            gcp_project_id=project_id, gcp_region=region, user_agent=IMAGEN4_USER_AGENT
        )

    def generate_image_from_text(
        self,
        model: str,
        prompt: str,
        person_generation: str,
        aspect_ratio: str,
        number_of_images: int,
        negative_prompt: str,
        seed: Optional[int],
        enhance_prompt: bool,
        add_watermark: bool,
        output_image_type: str,
        safety_filter_level: str,
    ) -> List[Image.Image]:
        """
        Generate image from text prompt using Imagen4.

        Args:
            model: Imagen4 model it. There are three as of Jul 1, 2025.
            prompt: The text prompt for image generation.
            person_generation: Controls whether the model can generate people.
            aspect_ratio: The desired aspect ratio of the images.
            number_of_images: The number of images to generate (1-4).
            negative_prompt: A prompt to guide the model to avoid generating certain things.
            seed: Optional. A seed for reproducible image generation.
            enhance_prompt: Whether to enhance the prompt automatically.
            add_watermark: Whether to add a watermark to the generated images.
            output_image_type: The desired output image format (PNG or JPEG).
            safety_filter_level: The safety filter strictness.

        Returns:
            A list of PIL Image objects. Returns an empty list on failure.

        Raises:
            APIInputError: If parameters are invalid.
            APIExecutionError: If the API call fails due to quota, permissions, or server issues.
        """
        if not (1 <= number_of_images <= 4):
            raise APIInputError(
                f"number_of_images must be between 1 and 4, but got {number_of_images}."
            )
        if seed and add_watermark:
            raise APIInputError("Seed is not supported when add_watermark is enabled.")

        output_image_type = output_image_type.upper()
        if output_image_type == "PNG":
            output_mime_type = "image/png"
        elif output_image_type == "JPEG":
            output_mime_type = "image/jpeg"
        else:
            raise APIInputError(f"Unsupported image format: {output_image_type}")

        model = Imagen4Model[model]
        if model == Imagen4Model.IMAGEN_4_ULTRA_PREVIEW.value and number_of_images > 1:
            raise APIInputError("Ultra model only generates one image at a time.")

        return utils.generate_image_from_text(
            client=self.client,
            model=model,
            prompt=prompt,
            person_generation=person_generation,
            aspect_ratio=aspect_ratio,
            number_of_images=number_of_images,
            negative_prompt=negative_prompt,
            seed=seed,
            enhance_prompt=enhance_prompt,
            add_watermark=add_watermark,
            output_image_type=output_mime_type,
            safety_filter_level=safety_filter_level,
        )
