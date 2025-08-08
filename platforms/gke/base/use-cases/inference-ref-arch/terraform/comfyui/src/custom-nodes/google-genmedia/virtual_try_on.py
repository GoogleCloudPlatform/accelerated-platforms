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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import utils
from google.api_core.client_info import ClientInfo
from google.cloud import aiplatform
from PIL import Image as PIL_Image

from .config import get_gcp_metadata
from .constants import MAX_SEED, VTO_USER_AGENT


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
            aiplatform.init(project=self.project_id, location=self.location)
            self.api_regional_endpoint = f"{self.location}-aiplatform.googleapis.com"
            self.client_options = {"api_endpoint": self.api_regional_endpoint}
            self.client_info = ClientInfo(user_agent=VTO_USER_AGENT)
            self.client = aiplatform.gapic.PredictionServiceClient(
                client_options=self.client_options, client_info=self.client_info
            )
            self.model_endpoint = f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/virtual-try-on-exp-05-31"
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
    CATEGORY = "Google AI/use-cases"

    def generate_and_return_image(
        self,
        person_image: torch.Tensor,
        product_image: torch.Tensor,
        base_steps: int,
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
            person_image: The image of the person to try the virtual try-on.
            product_image: The image of the product for the person to try-on.
            base_steps: integer
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
        # Re-initialize the client to avoid re-launching the node when the customers
        # provide gcp_project_id and gcp_region first and then remove them to use the defaults.
        try:
            init_project_id = gcp_project_id if gcp_project_id else None
            init_region = gcp_region if gcp_region else None
            self.__init__(gcp_project_id=init_project_id, gcp_region=init_region)
        except Exception as e:
            return (
                f"Error re-initializing Prediction client with provided GCP credentials: {e}",
            )
        instances = []
        p_gen_enum = getattr(types.PersonGeneration, person_generation)

        seed_for_api = seed if seed != 0 else None

        if person_image and product_image:
            person_image_bytes = utils.tensor_to_pil_to_bytes(person_image)
            product_image_bytes = utils.tensor_to_pil_to_bytes(product_image)
            instance = {
                "personImage": {"image": {"bytesBase64Encoded": person_image_bytes}},
                "productImages": [
                    {"image": {"bytesBase64Encoded": product_image_bytes}}
                ],
            }
            instances.append(instance)
        else:
            raise ValueError("Both person_image and product_image must be set.")

        parameters = {"sampleCount": number_of_images}
        parameters["baseSteps"] = base_steps
        parameters["safetySetting"] = safety_filter_level
        parameters["personGeneration"] = p_gen_enum
        parameters["aspect_ratio"] = aspect_ratio
        parameters["negative_prompt"] = negative_prompt
        parameters["seed"] = seed_for_api
        parameters["enhance_prompt"] = enhance_prompt
        parameters["add_watermark"] = add_watermark
        parameters["output_image_type"] = output_image_type

        try:
            response = self.client.predict(
                endpoint=self.model_endpoint, instances=instances, parameters=parameters
            )
            image_tensors = []
            for prediction in response.predictions:
                base64_image = prediction["bytesBase64Encoded"]
                image_data = base64.b64decode(base64_image)
                # Open the image data as a PIL Image.
                pil_image = Image.open(io.BytesIO(image_data)).convert("RGBA")
                # Convert the PIL Image to a NumPy array and normalize to [0, 1].
                image_array = np.array(pil_image).astype(np.float32) / 255.0
                # Convert the NumPy array to a torch.Tensor and add a batch dimension.
                tensor = torch.from_numpy(image_array)[None,]
                image_tensors.append(tensor)
            if not image_tensors:
                print("API did not return any images.")
                return (torch.zeros(1, 64, 64, 3, dtype=torch.float32),)

            batch_tensor = torch.cat(image_tensors, 0)
            return (batch_tensor,)
        except Exception as e:
            raise RuntimeError(f"Error occurred during image generation: {e}")


NODE_CLASS_MAPPINGS = {"VirtualTryOn": VirtualTryOn}

NODE_DISPLAY_NAME_MAPPINGS = {"VirtualTryOn": "Virtual try-on"}
