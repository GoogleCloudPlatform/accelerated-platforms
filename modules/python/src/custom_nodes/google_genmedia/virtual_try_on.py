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

import base64
import io
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import aiplatform
from google.genai import types
from PIL import Image

from . import utils
from .config import get_gcp_metadata
from .constants import MAX_SEED, VTO_MODEL, VTO_USER_AGENT


class VirtualTryOn:
    """
    A ComfyUI node for virtual try on.
    """

    def __init__(
        self, gcp_project_id: Optional[str] = None, gcp_region: Optional[str] = None
    ):
        """
        Initializes the Gemini client.

        Args:
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.

        Raises:
            ValueError: If GCP Project or region cannot be determined.
        """
        self.project_id = gcp_project_id
        self.region = gcp_region

        if not self.project_id:
            self.project_id = get_gcp_metadata("project/project-id")
        if not self.region:
            self.region = "-".join(
                get_gcp_metadata("instance/zone").split("/")[-1].split("-")[:-1]
            )

        if not self.project_id:
            raise ValueError("GCP Project is required and could not be determined.")
        if not self.region:
            raise ValueError("GCP region is required and could not be determined.")

        print(f"Project is {self.project_id}, region is {self.region}")
        try:
            aiplatform.init(project=self.project_id, location=self.region)
            self.api_regional_endpoint = f"{self.region}-aiplatform.googleapis.com"
            self.client_options = {"api_endpoint": self.api_regional_endpoint}
            self.client_info = ClientInfo(user_agent=VTO_USER_AGENT)
            self.client = aiplatform.gapic.PredictionServiceClient(
                client_options=self.client_options, client_info=self.client_info
            )
            self.model_endpoint = f"projects/{self.project_id}/locations/{self.region}/publishers/google/models/{VTO_MODEL}"
            print(
                f"Prediction client initiated on project : {self.project_id}, location: {self.region}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Prediction client for Vertex AI: {e}"
            )

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        """
        Defines the input types and widgets for the ComfyUI node.

        Returns:
            A dictionary specifying the required and optional input parameters.
        """
        return {
            "required": {
                "person_image": ("IMAGE",),
                "product_image": ("IMAGE",),
                "base_steps": ("INT", {"default": 32, "min": 1, "max": 50}),
                "person_generation": (
                    ["ALLOW_ADULT", "DONT_ALLOW"],
                    {"default": "ALLOW_ADULT"},
                ),
                "number_of_images": ("INT", {"default": 1, "min": 1, "max": 4}),
            },
            "optional": {
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "0 seed let's Imagen3 API handle randomness. Seed works with enhance_prompt disabled",
                    },
                ),
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
    CATEGORY = "Google AI/Use-cases"

    def generate_and_return_image(
        self,
        person_image: torch.Tensor,
        product_image: torch.Tensor,
        base_steps: int,
        person_generation: str,
        number_of_images: int,
        seed: int = 0,
        safety_filter_level: str = "BLOCK_MEDIUM_AND_ABOVE",
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[torch.Tensor,]:
        """
        Generates images for one person by trying on a batch of product images,
        one API call at a time.
        """
        try:
            # Re-initialize the client if needed
            init_project_id = gcp_project_id if gcp_project_id else None
            init_region = gcp_region if gcp_region else None
            self.__init__(gcp_project_id=init_project_id, gcp_region=init_region)
        except Exception as e:
            raise RuntimeError(f"Error re-initializing client: {e}")

        # Validate that the input tensors contain data
        if not (person_image.numel() > 0 and product_image.numel() > 0):
            raise ValueError(
                "Both person_image and product_image must be valid, non-empty images."
            )

        person_image_base64 = utils.tensor_to_pil_to_base64(person_image)

        all_generated_tensors = []

        # We will loop through each product image and make an API call with the same personImage and different productImages
        print(f"Beginning batch job for {product_image.shape[0]} product image(s).")
        for i in range(product_image.shape[0]):
            single_product_tensor = product_image[i : i + 1]
            print(f"Processing image {i+1} of {product_image.shape[0]}...")
            product_image_base64 = utils.tensor_to_pil_to_base64(single_product_tensor)
            instances = [
                {
                    "personImage": {
                        "image": {"bytesBase64Encoded": person_image_base64}
                    },
                    "productImages": [
                        {"image": {"bytesBase64Encoded": product_image_base64}}
                    ],
                }
            ]
            parameters = {
                "sampleCount": number_of_images,
                "baseSteps": base_steps,
                "safetySetting": safety_filter_level,
                "personGeneration": person_generation,
                "seed": seed if seed != 0 else None,
            }

            try:
                response = self.client.predict(
                    endpoint=self.model_endpoint,
                    instances=instances,
                    parameters=parameters,
                )
                for prediction in response.predictions:
                    base64_image_string = prediction["bytesBase64Encoded"]
                    tensor = utils.base64_to_pil_to_tensor(base64_image_string)
                    all_generated_tensors.append(tensor)
            except Exception as e:
                print(f"Could not generate image for product {i+1}. Error: {e}")
                continue

        # After the loop, check if we got any results at all
        if not all_generated_tensors:
            raise RuntimeError(
                "Image generation failed for all product images in the batch."
            )

        final_batch_tensor = torch.cat(all_generated_tensors, 0)
        print(
            f"Successfully generated {final_batch_tensor.shape[0]} image(s) in total."
        )
        return (final_batch_tensor,)


NODE_CLASS_MAPPINGS = {"VirtualTryOn": VirtualTryOn}

NODE_DISPLAY_NAME_MAPPINGS = {"VirtualTryOn": "Virtual try-on"}
