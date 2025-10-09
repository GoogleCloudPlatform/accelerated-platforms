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

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from google.genai import types

from .constants import MAX_SEED
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .imagen3_api import Imagen3API


class Imagen3TextToImageNode:
    """
    A ComfyUI node for generating images from text prompts using the Google Imagen API.
    """

    def __init__(self) -> None:
        """
        Initializes the Imagen3TextToImageNode.
        """
        pass

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        """
        Defines the input types and widgets for the ComfyUI node.

        Returns:
            A dictionary specifying the required and optional input parameters.
        """
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A vivid landscape painting of a futuristic city",
                    },
                ),
                "person_generation": (
                    ["ALLOW_ADULT", "DONT_ALLOW"],
                    {"default": "ALLOW_ADULT"},
                ),
                "aspect_ratio": (
                    ["1:1", "16:9", "4:3", "3:4", "9:16"],
                    {"default": "16:9"},
                ),
                "number_of_images": ("INT", {"default": 1, "min": 1, "max": 4}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "0 seed let's Imagen3 API handle randomness. Seed works with enhance_prompt disabled",
                    },
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "add_watermark": ("BOOLEAN", {"default": False}),
                "output_image_type": (["PNG", "JPEG"], {"default": "PNG"}),
                "safety_filter_level": (
                    [
                        "BLOCK_LOW_AND_ABOVE",
                        "BLOCK_MEDIUM_AND_ABOVE",
                        "BLOCK_ONLY_HIGH",
                        "BLOCK_NONE",
                    ],
                    {"default": "BLOCK_MEDIUM_AND_ABOVE"},
                ),
                "gcp_project_id": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "GCP project id where Vertex AI API will query Imagen",
                    },
                ),
                "gcp_region": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "GCP region for Vertex AI API",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("Generated Image",)

    FUNCTION = "generate_and_return_image"
    CATEGORY = "Google AI/Imagen3"

    def generate_and_return_image(
        self,
        prompt: str,
        person_generation: str = "DONT_ALLOW",
        aspect_ratio: str = "16:9",
        number_of_images: int = 4,
        negative_prompt: Optional[str] = None,
        seed: int = 0,
        enhance_prompt: bool = True,
        add_watermark: bool = False,
        output_image_type: str = "PNG",
        safety_filter_level: str = "BLOCK_MEDIUM_AND_ABOVE",
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[torch.Tensor,]:
        """
        Generates images based on the provided parameters using the Imagen API
        and returns them as a PyTorch tensor suitable for ComfyUI.

        Args:
            prompt: The text prompt for image generation.
            person_generation: Controls whether the model can generate people.
            aspect_ratio: The desired aspect ratio of the images.
            number_of_images: The number of images to generate (1-4).
            negative_prompt: A prompt to guide the model to avoid generating certain things.
            seed: A seed for reproducible image generation. If 0, Imagen API handles randomness.
            enhance_prompt: Whether to enhance the prompt automatically.
            add_watermark: Whether to add a watermark to the generated images.
            output_image_type: The desired output image format (PNG or JPEG).
            safety_filter_level: The safety filter strictness.
            gcp_project_id: GCP project ID where the Imagen will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Imagen

        Returns:
            A tuple containing a PyTorch tensor of the generated images,
            formatted as (batch_size, height, width, channels).

        Raises:
            RuntimeError: If API configuration fails, or if image generation encounters an API error.
        """
        try:
            imagen_api = Imagen3API(project_id=gcp_project_id, region=gcp_region)
        except ConfigurationError as e:
            raise RuntimeError(f"Imagen API Configuration Error: {e}") from e

        p_gen_enum = getattr(types.PersonGeneration, person_generation)

        seed_for_api = seed if seed != 0 else None

        try:
            pil_images = imagen_api.generate_image_from_text(
                prompt=prompt,
                person_generation=p_gen_enum,
                aspect_ratio=aspect_ratio,
                number_of_images=number_of_images,
                negative_prompt=negative_prompt,
                seed=seed_for_api,
                enhance_prompt=enhance_prompt,
                add_watermark=add_watermark,
                output_image_type=output_image_type,
                safety_filter_level=safety_filter_level,
            )
        except APIInputError as e:
            raise RuntimeError(f"Imagen API Input Error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"Imagen API Execution Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during image generation: {e}"
            ) from e

        if not pil_images:
            raise RuntimeError(
                "Imagen API failed to generate images or generated no valid images."
            )

        output_tensors: List[torch.Tensor] = []
        for img in pil_images:
            img = img.convert("RGB")
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)[None,]
            output_tensors.append(img_tensor)

        batched_images_tensor = torch.cat(output_tensors, dim=0)
        return (batched_images_tensor,)


NODE_CLASS_MAPPINGS = {"Imagen3TextToImageNode": Imagen3TextToImageNode}

NODE_DISPLAY_NAME_MAPPINGS = {"Imagen3TextToImageNode": "Imagen3 Text To Image"}
