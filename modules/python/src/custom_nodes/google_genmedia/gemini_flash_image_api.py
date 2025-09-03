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

# This is a preview version of Gemini 2.5 Flash Image custom node

from typing import List, Optional

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import torch

from . import utils

from .config import get_gcp_metadata
from .constants import GeminiFlashImageModel, GEMINI_25_FLASH_IMAGE_MAX_OUTPUT_TOKEN


class GeminiFlashImageAPI:
    """
    A class to interact with the Gemini Flash Image Preview model.
    """

    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """Initializes the Gemini 2.5 Flash Image Preview client.

        Args:
            project_id (Optional[str], optional): The GCP project ID. If not
              provided, it will be inferred from the environment. Defaults to None.
            region (Optional[str], optional): The GCP region. If not provided, it
              will be inferred from the environment. Defaults to None.

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

        self.client = genai.Client(
            vertexai=True, project=self.project_id, location=self.region
        )

        self.retry_count = 3
        self.retry_delay = 5

    def generate_image(
        self,
        model: str,
        prompt: str,
        temperature: float,
        top_p: float,
        top_k: int,
        hate_speech_threshold: str,
        harassment_threshold: str,
        sexually_explicit_threshold: str,
        dangerous_content_threshold: str,
        system_instruction: str,
        image: Optional[torch.Tensor] = None,
    ) -> List[Image.Image]:
        """Generates an image using the Gemini Flash Image model.

        Args:
            model: The name of the Gemini model to use. default: gemini-2.5-flash-image-preview
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
            image: An optional input image tensor for image-to-image tasks.
              Defaults to None.

        Returns:
            A list of generated PIL images.
        """
        model = GeminiFlashImageModel[model]

        generated_pil_images: List[Image.Image] = []

        generate_content_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=GEMINI_25_FLASH_IMAGE_MAX_OUTPUT_TOKEN,
            response_modalities=["TEXT", "IMAGE"],
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

        if image != None:
            num_images = image.shape[0]
            print(f"Number of Images {num_images}")
            for i in range(num_images):
                image_tensor = image[i].unsqueeze(0)
                image_to_b64 = utils.tensor_to_pil_to_base64(image_tensor)
                contents.append(
                    types.Part.from_bytes(data=image_to_b64, mime_type="image/png")
                )

        response = self.client.models.generate_content(
            model=model, contents=contents, config=generate_content_config
        )

        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print(part.text)
            elif part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                generated_pil_images.append(image)

        return generated_pil_images
