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

# This is a preview version of veo3 custom node
from typing import Any, Dict, List, Optional, Tuple

import torch

from .constants import (
    MAX_SEED,
    SUPPORTED_VIDEO_EXTENSIONS,
    VEO3_VALID_ASPECT_RATIOS,
    Veo3Model,
)
from .veo3_api import Veo3API


class Veo3TextToVideoNode:
    """
    A ComfyUI node for generating videos from text prompts using the Google Veo 3.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "model": (
                    [model.name for model in Veo3Model],
                    {"default": Veo3Model.VEO_3_PREVIEW.name},
                ),
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (VEO3_VALID_ASPECT_RATIOS, {"default": "16:9"}),
                "output_resolution": (["720p", "1080p"], {"default": "720p"}),
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
                    {"default": 8, "min": 4, "max": 8, "step": 2},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        prompt: str = "A drone shot smoothly flies through an ancient, mist-shrouded jungle at dawn.",
        aspect_ratio: str = "16:9",
        output_resolution: str = "720p",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from a text prompt using the Google Veo 3.0 API.

        Args:
            model: Veo3 model
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            output_resolution: The resolution of the generated video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
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
            RuntimeError: If API initialization fails, or if video generation encounters an error.
        """
        try:
            api = Veo3API(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            # Catch any exception from Veo3API.__init__ (ValueError, RuntimeError)
            raise RuntimeError(f"Failed to initialize Veo API: {e}")

        seed_for_api = seed if seed != 0 else None

        try:
            video_paths = api.generate_video_from_text(
                model=model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                output_resolution=output_resolution,
                compression_quality=compression_quality,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                generate_audio=generate_audio,
                enhance_prompt=enhance_prompt,
                sample_count=sample_count,
                output_gcs_uri=output_gcs_uri,
                negative_prompt=negative_prompt,
                seed=seed_for_api,
            )
        except ValueError as e:
            raise RuntimeError(f"Video generation configuration error: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Veo API error: {e}")
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during video generation: {e}"
            )

        return (video_paths,)


class Veo3GcsUriImageToVideoNode:
    """
    A ComfyUI node for generating videos from a Google Cloud Storage (GCS) image URI
    using the Google Veo 3.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "model": (
                    [model.name for model in Veo3Model],
                    {"default": Veo3Model.VEO_3_PREVIEW.name},
                ),
                "gcsuri": (
                    "STRING",
                    {"default": "", "tooltip": "GCS URI for the Image"},
                ),
                "image_format": (
                    ["PNG", "JPEG", "MP4"],
                    {"default": "PNG", "tooltip": "mime type of the image"},
                ),
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (VEO3_VALID_ASPECT_RATIOS, {"default": "16:9"}),
                "output_resolution": (["720p", "1080p"], {"default": "720p"}),
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
                    {"default": 8, "min": 4, "max": 8, "step": 2},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        gcsuri: str = "",
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        output_resolution: str = "720p",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from a GCS image URI using the Google Veo 3.0 API.

        Args:
            model: Veo3 model
            gcsuri: The GCS URI of the input image.
            image_format: The format of the input image.
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            output_resolution: The resolution of the generated video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
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
            RuntimeError: If API initialization fails, or if video generation encounters an error.
        """
        try:
            api = Veo3API(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Veo API: {e}")

        seed_for_api = seed if seed != 0 else None

        try:
            video_paths = api.generate_video_from_gcsuri_image(
                model=model,
                gcsuri=gcsuri,
                image_format=image_format,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                output_resolution=output_resolution,
                compression_quality=compression_quality,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                generate_audio=generate_audio,
                enhance_prompt=enhance_prompt,
                sample_count=sample_count,
                output_gcs_uri=output_gcs_uri,
                negative_prompt=negative_prompt,
                seed=seed_for_api,
            )
        except ValueError as e:
            raise RuntimeError(f"Video generation configuration error: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Video generation API error: {e}")
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during video generation: {e}"
            )

        return (video_paths,)


class Veo3ImageToVideoNode:
    """
    A ComfyUI node for generating videos from an input image (torch.Tensor)
    using the Google Veo 3.0 API.
    """

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "model": (
                    [model.name for model in Veo3Model],
                    {"default": Veo3Model.VEO_3_PREVIEW.name},
                ),
                "image": ("IMAGE",),
                "image_format": (
                    ["PNG", "JPEG", "MP4"],
                    {"default": "PNG", "tooltip": "mime type of the image"},
                ),
                "prompt": ("STRING", {"multiline": True}),
                "aspect_ratio": (VEO3_VALID_ASPECT_RATIOS, {"default": "16:9"}),
                "output_resolution": (["720p", "1080p"], {"default": "720p"}),
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
                    {"default": 8, "min": 4, "max": 8, "step": 2},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        image: torch.Tensor = None,
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        output_resolution: str = "720p",
        compression_quality: str = "optimized",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        seed: Optional[int] = None,
        output_gcs_uri: str = "",
        negative_prompt: Optional[str] = None,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates a video from an input image (torch.Tensor) using the Google Veo 3.0 API.

        Args:
            model: Veo3 model
            image: The input image as a torch.Tensor.
            image_format: The format of the input image.
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            output_resolution: The resolution of the generated video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            seed: An optional seed for reproducible video generation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            gcp_project_id: GCP project ID where the Veo will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Veo

        Returns:
            A tuple containing a list of file paths to the generated videos.

        Raises:
            RuntimeError: If API initialization fails, or if video generation encounters an error.
        """
        try:
            api = Veo3API(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Veo API: {e}")

        seed_for_api = seed if seed != 0 else None

        all_generated_video_paths: List[str] = []
        num_input_images = image.shape[0]
        print(f"Received {num_input_images} input image(s) for video generation.")
        for i in range(num_input_images):
            single_image_tensor = image[i].unsqueeze(0)
            current_image = image[i]
            print(
                f"Processing image {i+1}/{num_input_images} (shape: {single_image_tensor.shape})..."
            )
            try:
                video_paths = api.generate_video_from_image(
                    model=model,
                    image=single_image_tensor,
                    image_format=image_format,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    output_resolution=output_resolution,
                    compression_quality=compression_quality,
                    person_generation=person_generation,
                    duration_seconds=duration_seconds,
                    generate_audio=generate_audio,
                    enhance_prompt=enhance_prompt,
                    sample_count=sample_count,
                    output_gcs_uri=output_gcs_uri,
                    negative_prompt=negative_prompt,
                    seed=seed_for_api,
                )
                all_generated_video_paths.extend(video_paths)
            except ValueError as e:
                raise RuntimeError(f"Video generation configuration error: {e}")
            except RuntimeError as e:
                raise RuntimeError(f"Video generation API error: {e}")
            except Exception as e:
                raise RuntimeError(
                    f"An unexpected error occurred during video generation: {e}"
                )

        return (all_generated_video_paths,)


NODE_CLASS_MAPPINGS = {
    "Veo3TextToVideoNode": Veo3TextToVideoNode,
    "Veo3GcsUriImageToVideoNode": Veo3GcsUriImageToVideoNode,
    "Veo3ImageToVideoNode": Veo3ImageToVideoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Veo3TextToVideoNode": "Veo3 Text To Video",
    "Veo3GcsUriImageToVideoNode": "Veo3 Image To Video (GcsUriImage)",
    "Veo3ImageToVideoNode": "Veo3 Image To Video",
}
