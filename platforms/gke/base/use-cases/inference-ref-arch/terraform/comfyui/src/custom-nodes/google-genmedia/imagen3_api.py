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

#  This is a preview version of Google GenAI custom nodes

from typing import List, Optional

from google import genai
from PIL import Image

from . import utils
from .config import get_gcp_metadata
from .constants import IMAGEN3_MODEL_ID, IMAGEN3_USER_AGENT


class Imagen3API:
    """
    A class to interact with the Imagen API for image generation.
    """

    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initializes the Imagen3API client.

        Args:
            project_id: The GCP project ID. If None, it will be retrieved from GCP metadata.
            region: The GCP region. If None, it will be retrieved from GCP metadata.

        Raises:
            ValueError: If GCP Project or region cannot be determined.
        """
        self.project_id = project_id or get_gcp_metadata("project/project-id")
        self.region = region or "-".join(
            get_gcp_metadata("instance/zone").split("/")[-1].split("-")[:-1]
        )
        if not self.project_id:
            raise ValueError("GCP Project is required")
        if not self.region:
            raise ValueError("GCP region is required")
        print(f"Project is {self.project_id}, region is {self.region}")
        http_options = genai.types.HttpOptions(
            headers={"user-agent": IMAGEN3_USER_AGENT}
        )
        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.region,
            http_options=http_options,
        )

        self.retry_count = 3  # Number of retries for quota errors
        self.retry_delay = 5  # Delay between retries (seconds)

    def generate_image_from_text(
        self,
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
        Generate image from text prompt using Imagen3.

        Args:
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
            ValueError: If `number_of_images` is not between 1 and 4,
                        if `seed` is provided with `add_watermark` enabled,
                        or if `output_image_type` is unsupported.
        """
        if not (1 <= number_of_images <= 4):
            raise ValueError(
                f"number_of_images must be between 1 and 4, but got {number_of_images}."
            )
        if seed and add_watermark:
            raise ValueError("Seed is not supported when add_watermark is enabled.")

        output_image_type = output_image_type.upper()
        if output_image_type == "PNG":
            output_mime_type = "image/png"
        elif output_image_type == "JPEG":
            output_mime_type = "image/jpeg"
        else:
            raise ValueError(f"Unsupported image format: {output_image_type}")

        return utils.generate_image_from_text(
            client=self.client,
            model=IMAGEN3_MODEL_ID,
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
            retry_count=self.retry_count,
            retry_delay=self.retry_delay,
        )
