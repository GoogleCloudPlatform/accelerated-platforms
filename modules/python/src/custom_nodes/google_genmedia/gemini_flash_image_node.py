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

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from .constants import GeminiFlashImageModel, ThresholdOptions
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
                    {
                        "default": GeminiFlashImageModel.GEMINI_25_FLASH_IMAGE_PREVIEW.name
                    },
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
        """Generates images using the Gemini Flash Image API and returns them.

        This method interfaces with the GeminiFlashImageAPI to generate images
        based on a prompt and other parameters. It then converts the generated
        PIL images into a PyTorch tensor suitable for use in ComfyUI.

        Args:
            model: The Gemini Flash Image model to use. default: gemini-2.5-flash-image-preview
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
            image: An optional input image tensor for image editing tasks.
              Defaults to None.
            gcp_project_id: The GCP project ID.
            gcp_region: The GCP region.

        Returns:
            A tuple containing a PyTorch tensor of the generated images,
            formatted as (batch_size, height, width, channels).
        """
        try:
            gemini_flash_image_api = GeminiFlashImageAPI(
                project_id=gcp_project_id, region=gcp_region
            )
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


NODE_CLASS_MAPPINGS = {"Gemini25FlashImage": Gemini25FlashImage}

NODE_DISPLAY_NAME_MAPPINGS = {"Gemini25FlashImage": "Gemini 2.5 Flash Image (🍌)"}
