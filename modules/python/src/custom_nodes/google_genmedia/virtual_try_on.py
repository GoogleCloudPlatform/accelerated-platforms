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

from typing import Any, Dict, Optional, Tuple

import torch

from . import exceptions, utils
from .config import GoogleGenAIBaseAPI
from .constants import MAX_SEED, VTO_MODEL, VTO_USER_AGENT
from .retry import retry_on_api_error


class VirtualTryOnAPI(GoogleGenAIBaseAPI):
    """API client for the Virtual Try-On model."""

    def __init__(
        self, gcp_project_id: Optional[str] = None, gcp_region: Optional[str] = None
    ):
        super().__init__(
            gcp_project_id=gcp_project_id,
            gcp_region=gcp_region,
            user_agent_suffix=VTO_USER_AGENT,
        )
        try:
            self.client = self.get_prediction_client()
            self.model_endpoint = f"projects/{self.project_id}/locations/{self.region}/publishers/google/models/{VTO_MODEL}"
            print(
                f"Prediction client initiated on project : {self.project_id}, location: {self.region}"
            )
        except Exception as e:
            raise exceptions.APIInitializationError(
                f"Failed to initialize Prediction client for Vertex AI: {e}"
            )

    @retry_on_api_error()
    def predict(self, instances, parameters):
        return self.client.predict(
            endpoint=self.model_endpoint,
            instances=instances,
            parameters=parameters,
        )


class VirtualTryOn:
    """
    A ComfyUI node for virtual try on.
    """

    def __init__(self):
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
                        "tooltip": "0 seed let's VTO API handle randomness. Seed works with enhance_prompt disabled",
                    },
                ),
                "add_watermark": ("BOOLEAN", {"default": False}),
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
        add_watermark: bool = False,
        safety_filter_level: str = "BLOCK_MEDIUM_AND_ABOVE",
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[torch.Tensor,]:
        """
        This function iterates through each provided product image, makes an API call to the
        Virtual Try-On service, and returns the generated images as a concatenated tensor.

        Args:
            person_image: A PyTorch tensor representing the image of the person.
            product_image: A PyTorch tensor representing the product image(s).
            base_steps: The number of base steps for image generation.
            person_generation: A string indicating the safety level for person generation,
                            e.g., 'ALLOW_ADULT' or 'DONT_ALLOW'.
            number_of_images: The number of images to generate for each product.
            seed: The seed for the image generation process. A value of 0 lets the API
              handle randomness.
            add_watermark: A boolean indicating whether to add a watermark to the output image.
            safety_filter_level: The safety filter level for the generated images, with options
                            like 'BLOCK_LOW_AND_ABOVE', 'BLOCK_MEDIUM_AND_ABOVE', etc.
            gcp_project_id: An optional string for the GCP project ID. If provided, it overrides
                        the project ID determined from metadata.
            gcp_region: An optional string for the GCP region. If provided, it overrides the
                    region determined from metadata.

        Returns:
            A tuple containing a concatenated PyTorch tensor of all generated images.

        Raises:
            RuntimeError: If the client fails to initialize or if image generation fails for
                        all products in the batch.
            ValueError: If `person_image` or `product_image` are empty, or if `seed` is used
                        when `add_watermark` is enabled.
        """
        try:
            vto_api = VirtualTryOnAPI(
                gcp_project_id=gcp_project_id, gcp_region=gcp_region
            )
        except exceptions.APIInitializationError as e:
            raise RuntimeError(f"Error initializing client: {e}")

        # Validate that the input tensors contain data
        if not (person_image.numel() > 0 and product_image.numel() > 0):
            raise exceptions.ConfigurationError(
                "Both person_image and product_image must be valid, non-empty images."
            )
        seed_for_api = seed if seed != 0 else None
        if seed_for_api and add_watermark:
            raise ValueError("Seed is not supported when add_watermark is enabled.")

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
                "seed": seed_for_api,
                "addWatermark": add_watermark,
                "safety_filter_level": safety_filter_level,
            }
            try:
                response = vto_api.predict(
                    instances=instances,
                    parameters=parameters,
                )
                for prediction in response.predictions:
                    base64_image_string = prediction["bytesBase64Encoded"]
                    tensor = utils.base64_to_pil_to_tensor(base64_image_string)
                    all_generated_tensors.append(tensor)
            except (exceptions.APICallError, exceptions.ConfigurationError) as e:
                print(f"Could not generate image for product {i+1}. Error: {e}")
                continue

        # After the loop, check if we got any results at all
        if not all_generated_tensors:
            raise exceptions.APICallError(
                "Image generation failed for all product images in the batch."
            )

        try:
            final_batch_tensor = torch.cat(all_generated_tensors, 0)
            print(
                f"Successfully generated {final_batch_tensor.shape[0]} image(s) in total."
            )
            return (final_batch_tensor,)
        except Exception as e:
            raise RuntimeError(
                f"Failed to concatenate generated images into a batch: {e}"
            )


NODE_CLASS_MAPPINGS = {"VirtualTryOn": VirtualTryOn}

NODE_DISPLAY_NAME_MAPPINGS = {"VirtualTryOn": "Virtual try-on"}
