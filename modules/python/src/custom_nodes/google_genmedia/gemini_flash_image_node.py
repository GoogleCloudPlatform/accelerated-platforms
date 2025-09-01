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

# This is a preview version of imagen4 custom node

from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
import numpy as np
import torch
from google.genai import types

from .constants import (
    MAX_SEED, 
    GeminiFlashImageModel,     
    ThresholdOptions
)
from .gemini_flash_image_api import GeminiFlashImageAPI


class Gemini25FlashImage:
    """
    A ComfyUI node for generating images from text prompts using the Google Imagen API.
    """

    def __init__(self) -> None:
        """
        Initializes the ImagenTextToImageNode.
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
                "model": (
                    [model.name for model in GeminiFlashImageModel],
                    {"default": GeminiFlashImageModel.GEMINI_25_FLASH_IMAGE_PREVIEW.name},
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A vivid landscape painting of a futuristic city",
                    },
                ),
                "temperature": (
                    "FLOAT",
                    {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "top_p": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "top_k": ("INT", {"default": 32, "min": 1, "max": 64}),
            },
            "optional": {
                "image": ("IMAGE",),
                # Safety Settings
                "harassment_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "hate_speech_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "sexually_explicit_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "dangerous_content_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "system_instruction": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Optional system instruction for the model",
                    },
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
                        "default": "global",
                        "tooltip": "GCP region for Vertex AI API",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("Generated Image",)

    FUNCTION = "generate_and_return_image"
    CATEGORY = "Google AI/GeminiFlashImage"

    def generate_and_return_image(
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
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[torch.Tensor,]:
        """
        Generates images based on the provided parameters using the Imagen API
        and returns them as a PyTorch tensor suitable for ComfyUI.

        Args:
            model: Imagen4 model it. There are three as of Jul 1, 2025.
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
        """
        try:
            gemini_flash_image_api = GeminiFlashImageAPI(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Imagen API client for node execution: {e}"
            )
            
        if image != None:
            print(type(image))

        try:
            pil_images = gemini_flash_image_api.generate_image(
                model,
                prompt,
                temperature,
                top_p,
                top_k,
                hate_speech_threshold,
                harassment_threshold,
                sexually_explicit_threshold,
                dangerous_content_threshold,
                system_instruction,
                image,
            )
        except Exception as e:
            raise RuntimeError(f"Error occurred during image generation: {e}")
            # return (torch.empty(0, 640, 640, 3),)

        if not pil_images:
            raise RuntimeError(
                "Imagen API failed to generate images or generated no valid images."
            )

        output_tensors: List[torch.Tensor] = []
        for img in pil_images:
            img = img.convert("RGB")
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)[
                None,
            ]
            output_tensors.append(img_tensor)

        batched_images_tensor = torch.cat(output_tensors, dim=0)
        return (batched_images_tensor,)


NODE_CLASS_MAPPINGS = {"Gemin25FlashImage": Gemini25FlashImage}

NODE_DISPLAY_NAME_MAPPINGS = {"Gemin25FlashImage": "Gemini 2.5 Flash Image"}
