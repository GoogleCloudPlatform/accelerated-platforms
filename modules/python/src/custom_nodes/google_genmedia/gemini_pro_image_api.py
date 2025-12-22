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

# This is a preview version of Gemini 3 Pro Image custom node

from io import BytesIO
from typing import List, Optional

import torch
from google import genai
from google.api_core import exceptions as api_core_exceptions
from google.genai import types
from PIL import Image

from . import utils
from .base import VertexAIClient
from .constants import (
    GEMINI_3_PRO_IMAGE_MAX_OUTPUT_TOKEN,
    GEMINI_3_PRO_IMAGE_USER_AGENT,
    GeminiProImageModel,
)
from .custom_exceptions import ConfigurationError
from .logger import get_node_logger
from .retry import api_error_retry

logger = get_node_logger(__name__)


class GeminiProImageAPI(VertexAIClient):
    """
    A class to interact with the Gemini Pro Image Preview model.
    """

    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """Initializes the Gemini 3 Pro Image Preview client.
        Args:
            project_id (Optional[str], optional): The GCP project ID. If not provided, it will be inferred from the environment. Defaults to None.
            region (Optional[str], optional): The GCP region. If not provided, it will be inferred from the environment. Defaults to None.
        Raises:
            ConfigurationError: If GCP Project or region cannot be determined or client initialization fails.
        """
        super().__init__(
            gcp_project_id=project_id,
            gcp_region=region,
            user_agent=GEMINI_3_PRO_IMAGE_USER_AGENT,
        )

    @api_error_retry
    def generate_image(
        self,
        model: str,
        aspect_ratio: str,
        prompt: str,
        temperature: float,
        top_p: float,
        top_k: int,
        hate_speech_threshold: str,
        harassment_threshold: str,
        sexually_explicit_threshold: str,
        dangerous_content_threshold: str,
        system_instruction: str,
        image1: torch.Tensor,
        image2: Optional[torch.Tensor] = None,
        image3: Optional[torch.Tensor] = None,
    ) -> List[Image.Image]:
        """Generates an image using the Gemini Pro Image model.

        Args:
            model: The name of the Gemini model to use. default: gemini-3-pro-image-preview
            aspect_ratio: The desired aspect ratio of the output image.
            prompt: The text prompt for image generation.
            temperature: Controls randomness in token generation.
            top_p: The cumulative probability of tokens to consider for sampling.
            top_k: The number of highest probability tokens to consider for sampling.
            hate_speech_threshold: Safety threshold for hate speech.
            harassment_threshold: Safety threshold for harassment.
            sexually_explicit_threshold: Safety threshold for sexually explicit
              content.
            dangerous_content_threshold: Safety threshold for dangerous content.
            system_instruction: System-level instructions for the model.
            image1: An optional input image tensor. Defaults to None.
            image2: An optional second input image tensor. Defaults to None.
            image3: An optional third input image tensor. Defaults to None.

        Returns:
            A list of generated PIL images.

        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If the API call fails due to quota, permissions, or server issues.
        """
        model = GeminiProImageModel[model]

        generated_pil_images: List[Image.Image] = []

        generate_content_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=GEMINI_3_PRO_IMAGE_MAX_OUTPUT_TOKEN,
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            ),
            system_instruction=system_instruction,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold=hate_speech_threshold,
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold=dangerous_content_threshold,
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold=sexually_explicit_threshold,
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT", threshold=harassment_threshold
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_IMAGE_HATE", threshold=hate_speech_threshold
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT",
                    threshold=dangerous_content_threshold,
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_IMAGE_HARASSMENT",
                    threshold=harassment_threshold,
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT",
                    threshold=sexually_explicit_threshold,
                ),
            ],
        )

        contents = [types.Part.from_text(text=prompt)]

        for i, image_tensor in enumerate([image1, image2, image3]):
            if image_tensor is not None:
                for j in range(image_tensor.shape[0]):
                    single_image = image_tensor[j].unsqueeze(0)
                    image_bytes = utils.tensor_to_pil_to_bytes(single_image)
                    contents.append(
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                    )
                    logger.info(f"Appended image {i+1}, part {j+1} to contents.")

        response = self.client.models.generate_content(
            model=model, contents=contents, config=generate_content_config
        )

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                logger.info(f"response is {part.text}")
            elif part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                generated_pil_images.append(image)

        return generated_pil_images
