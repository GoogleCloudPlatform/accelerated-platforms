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

# This is a preview version of veo2 custom node

from typing import Any, Dict, List, Optional, Tuple

import torch

from .constants import MAX_SEED
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .logger import get_node_logger
from .veo2_api import Veo2API

logger = get_node_logger(__name__)


class Veo2TextToVideoNode:
    """
    A ComfyUI node for generating videos from text prompts using the Google Veo 2.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (["16:9", "9:16"], {"default": "16:9"}),
                "compression_quality": (
                    ["optimized", "lossless"],
                    {"default": "optimized"},
                ),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
                "output_gcs_uri": ("STRING", {"default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "0 seed let's Veo API handle randomness. Seed works with enhance_prompt disabled",
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
                        "default": "",
                        "tooltip": "GCP region for Vertex AI API",
                    },
                ),
            },
        }

    RETURN_TYPES = ("VEO_VIDEO",)
    RETURN_NAMES = ("video_paths",)
    FUNCTION = "generate"
    CATEGORY = "Google AI/Veo2"

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from a text prompt using the Google Veo 2.0 API.

        Args:
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.
            gcp_project_id: GCP project ID where the Veo will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Veo

        Returns:
            A tuple containing a list of file paths to the generated videos.

        Raises:
            RuntimeError: If API configuration fails, or if video generation encounters an API error.
        """
        try:
            api = Veo2API(project_id=gcp_project_id, region=gcp_region)
        except ConfigurationError as e:
            raise RuntimeError(f"Veo API Configuration Error: {e}") from e

        seed_for_api = seed if seed != 0 else None

        try:
            video_paths = api.generate_video_from_text(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                compression_quality=compression_quality,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                enhance_prompt=enhance_prompt,
                sample_count=sample_count,
                output_gcs_uri=output_gcs_uri,
                negative_prompt=negative_prompt,
                seed=seed_for_api,
            )
        except APIInputError as e:
            raise RuntimeError(f"Video generation configuration error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"Veo API error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during video generation: {e}"
            ) from e

        return (video_paths,)


class Veo2GcsUriImageToVideoNode:
    """
    A ComfyUI node for generating videos from a Google Cloud Storage (GCS) image URI
    using the Google Veo 2.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "gcsuri": (
                    "STRING",
                    {"default": "", "tooltip": "GCS URI for the Image"},
                ),
                "image_format": (
                    ["PNG", "JPEG", "MP4"],
                    {"default": "PNG", "tooltip": "mime type of the image"},
                ),
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (["16:9", "9:16"], {"default": "16:9"}),
                "compression_quality": (
                    ["optimized", "lossless"],
                    {"default": "optimized"},
                ),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
                "last_frame_gcsuri": (
                    "STRING",
                    {"default": "", "tooltip": "GCS URI for the last frame image"},
                ),
                "output_gcs_uri": ("STRING", {"default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "0 seed let's Veo API handle randomness. Seed works with enhance_prompt disabled",
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
                        "default": "",
                        "tooltip": "GCP region for Vertex AI API",
                    },
                ),
            },
        }

    RETURN_TYPES = ("VEO_VIDEO",)
    RETURN_NAMES = ("video_paths",)
    FUNCTION = "generate"
    CATEGORY = "Google AI/Veo2"

    def generate(
        self,
        gcsuri: str = "",
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        last_frame_gcsuri: str = "",
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from a GCS image URI using the Google Veo 2.0 API.

        Args:
            gcsuri: The GCS URI of the input image.
            image_format: The format of the input image.
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            last_frame_gcsuri: gcsuri of the last_frame image for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.
            gcp_project_id: GCP project ID where the Veo will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Veo

        Returns:
            A tuple containing a list of file paths to the generated videos.

        Raises:
            RuntimeError: If API configuration fails, or if video generation encounters an API error.
        """
        try:
            api = Veo2API(project_id=gcp_project_id, region=gcp_region)
        except ConfigurationError as e:
            raise RuntimeError(f"Veo API Configuration Error: {e}") from e

        seed_for_api = seed if seed != 0 else None

        try:
            video_paths = api.generate_video_from_gcsuri_image(
                gcsuri=gcsuri,
                image_format=image_format,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                compression_quality=compression_quality,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                enhance_prompt=enhance_prompt,
                sample_count=sample_count,
                last_frame_gcsuri=last_frame_gcsuri,
                output_gcs_uri=output_gcs_uri,
                negative_prompt=negative_prompt,
                seed=seed_for_api,
            )
        except APIInputError as e:
            raise RuntimeError(f"Video generation configuration error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"Video generation API error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during video generation: {e}"
            ) from e

        return (video_paths,)


class Veo2ImageToVideoNode:
    """
    A ComfyUI node for generating videos from an input image (torch.Tensor)
    using the Google Veo 2.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "image": ("IMAGE",),
                "image_format": (
                    ["PNG", "JPEG", "MP4"],
                    {"default": "PNG", "tooltip": "mime type of the image"},
                ),
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (["16:9", "9:16"], {"default": "16:9"}),
                "compression_quality": (
                    ["optimized", "lossless"],
                    {"default": "optimized"},
                ),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
                "last_frame": ("IMAGE",),
                "output_gcs_uri": ("STRING", {"default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "0 seed let's Veo API handle randomness. Seed works with enhance_prompt disabled",
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
                        "default": "",
                        "tooltip": "GCP region for Vertex AI API",
                    },
                ),
            },
        }

    RETURN_TYPES = ("VEO_VIDEO",)
    RETURN_NAMES = ("video_paths",)
    FUNCTION = "generate"
    CATEGORY = "Google AI/Veo2"

    def generate(
        self,
        image: torch.Tensor,
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        seed: Optional[int] = None,
        last_frame: Optional[torch.Tensor] = None,
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from an input image (torch.Tensor) using the Google Veo 2.0 API.

        Args:
            image: The input image as a torch.Tensor.
            image_format: The format of the input image.
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            seed: An optional seed for reproducible video generation.
            last_frame: last frame for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            gcp_project_id: GCP project ID where the Veo will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Veo

        Returns:
            A tuple containing a list of file paths to the generated videos.

        Raises:
            RuntimeError: If API configuration fails, or if video generation encounters an API error.
        """
        try:
            api = Veo2API(project_id=gcp_project_id, region=gcp_region)
        except ConfigurationError as e:
            raise RuntimeError(f"Veo API Configuration Error: {e}") from e

        seed_for_api = seed if seed != 0 else None

        all_generated_video_paths: List[str] = []
        num_input_images = image.shape[0]
        logger.info(f"Received {num_input_images} input image(s) for video generation.")
        for i in range(num_input_images):
            single_image_tensor = image[i].unsqueeze(0)
            logger.info(
                f"Processing image {i+1}/{num_input_images} (shape: {single_image_tensor.shape})..."
            )
            try:
                video_paths = api.generate_video_from_image(
                    image=single_image_tensor,
                    image_format=image_format,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    compression_quality=compression_quality,
                    person_generation=person_generation,
                    duration_seconds=duration_seconds,
                    enhance_prompt=enhance_prompt,
                    sample_count=sample_count,
                    last_frame=last_frame,
                    output_gcs_uri=output_gcs_uri,
                    negative_prompt=negative_prompt,
                    seed=seed_for_api,
                )
                all_generated_video_paths.extend(video_paths)
            except APIInputError as e:
                raise RuntimeError(f"Video generation configuration error: {e}") from e
            except APIExecutionError as e:
                raise RuntimeError(f"Video generation API error: {e}") from e
            except Exception as e:
                raise RuntimeError(
                    f"An unexpected error occurred during video generation: {e}"
                ) from e

        return (all_generated_video_paths,)


NODE_CLASS_MAPPINGS = {
    "Veo2TextToVideoNode": Veo2TextToVideoNode,
    "Veo2GcsUriImageToVideoNode": Veo2GcsUriImageToVideoNode,
    "Veo2ImageToVideoNode": Veo2ImageToVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Veo2TextToVideoNode": "Veo2 Text To Video",
    "Veo2GcsUriImageToVideoNode": "Veo2 Image To Video (GcsUriImage)",
    "Veo2ImageToVideoNode": "Veo2 Image To Video",
}
