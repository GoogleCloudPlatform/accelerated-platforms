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

from typing import List, Optional

import torch
from google import genai

from . import utils
from .base import VertexAIClient
from .constants import (
    OUTPUT_RESOLUTION,
    VEO3_USER_AGENT,
    VEO3_VALID_ASPECT_RATIOS,
    VEO3_VALID_DURATION_SECONDS,
    VEO3_VALID_SAMPLE_COUNT,
    Veo3Model,
)
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .logger import get_node_logger

logger = get_node_logger(__name__)


class Veo3API(VertexAIClient):
    """
    A client for interacting with the Google Veo 3.1 API for video generation.
    """

    def __init__(
        self, project_id: Optional[str] = None, region: Optional[str] = None
    ) -> None:
        """
        Initializes the Veo3API client.

        Args:
            project_id: The GCP project ID. If None, it will be retrieved from GCP metadata.
            region: The GCP region. If None, it will be retrieved from GCP metadata.

        Raises:
            ConfigurationError: If GCP Project or region cannot be determined or client initialization fails.
        """
        super().__init__(
            gcp_project_id=project_id, gcp_region=region, user_agent=VEO3_USER_AGENT
        )

    def generate_video_from_text(
        self,
        model: str,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        generate_audio: bool,
        enhance_prompt: bool,
        sample_count: int,
        output_gcs_uri: str,
        output_resolution: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from a text prompt using the Veo 3.1 API.

        Args:
            model: Veo3 model.
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video (e.g., "16:9", "1:1").
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people ("allow" or "dont_allow").
            duration_seconds: The desired duration of the video in seconds (5-8 seconds).
            generate_audio: Flag to generate audio.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate (1-4).
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            output_resolution: The resolution of the generated video.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.

        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            raise APIInputError("Prompt cannot be empty for text-to-video generation.")
        if duration_seconds not in VEO3_VALID_DURATION_SECONDS:
            raise APIInputError(
                f"duration_seconds must be one of {VEO3_VALID_DURATION_SECONDS}, but got {duration_seconds}."
            )
        if sample_count not in VEO3_VALID_SAMPLE_COUNT:
            raise APIInputError(
                f"sample_count must be one of {VEO3_VALID_SAMPLE_COUNT} for Veo3, but got {sample_count}."
            )
        if aspect_ratio not in VEO3_VALID_ASPECT_RATIOS:
            raise APIInputError(
                f"Veo3 can only generate videos of aspect ratios {VEO3_VALID_ASPECT_RATIOS}. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise APIInputError(
                f"Veo3 can only generate videos of resolution {OUTPUT_RESOLUTION}. You passed aspect ratio {output_resolution}."
            )

        model = Veo3Model[model]

        return utils.generate_video_from_text(
            client=self.client,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            duration_seconds=duration_seconds,
            generate_audio=generate_audio,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            output_gcs_uri=output_gcs_uri,
            output_resolution=output_resolution,
            negative_prompt=negative_prompt,
            seed=seed,
        )

    def generate_video_from_image(
        self,
        model: str,
        image: torch.Tensor,
        image_format: str,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        generate_audio: bool,
        enhance_prompt: bool,
        sample_count: int,
        last_frame: torch.Tensor,
        output_gcs_uri: str,
        output_resolution: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from an image input (as a torch.Tensor) using the Veo 3.1 API.

        Args:
            model: Veo3 model.
            image: The input image as a torch.Tensor (ComfyUI format).
            image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            last_frame: last frame for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            output_resolution: The resolution of the generated video.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.

        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            logger.warning(
                "Prompt is empty for image-to-video. Veo might use default interpretation of image."
            )
        if duration_seconds not in VEO3_VALID_DURATION_SECONDS:
            raise APIInputError(
                f"duration_seconds must be one of {VEO3_VALID_DURATION_SECONDS}, but got {duration_seconds}."
            )
        if sample_count not in VEO3_VALID_SAMPLE_COUNT:
            raise APIInputError(
                f"sample_count must be one of {VEO3_VALID_SAMPLE_COUNT} for Veo3, but got {sample_count}."
            )

        if image is None:
            raise APIInputError("Image input (torch.Tensor) cannot be None.")
        if aspect_ratio not in VEO3_VALID_ASPECT_RATIOS:
            raise APIInputError(
                f"Veo3 can only generate videos of aspect ratios {VEO3_VALID_ASPECT_RATIOS}. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise APIInputError(
                f"Veo3 can only generate videos of resolution {OUTPUT_RESOLUTION}. You passed aspect ratio {output_resolution}."
            )
        model = Veo3Model[model]
        return utils.generate_video_from_image(
            client=self.client,
            model=model,
            image=image,
            image_format=image_format,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            duration_seconds=duration_seconds,
            generate_audio=generate_audio,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            last_frame=last_frame,
            output_gcs_uri=output_gcs_uri,
            output_resolution=output_resolution,
            negative_prompt=negative_prompt,
            seed=seed,
        )

    def generate_video_from_references(
        self,
        model: str,
        prompt: str,
        image1: torch.Tensor,
        image_format: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        generate_audio: bool,
        enhance_prompt: bool,
        sample_count: int,
        output_gcs_uri: str,
        output_resolution: str,
        image2: Optional[torch.Tensor],
        image3: Optional[torch.Tensor],
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates a video from the references.

        Args:
            model: Veo3 model.
            prompt: The text prompt for video generation.
            image1: The first reference image as a torch.Tensor.
            image_format: The format of the input images.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality (optimized or lossless).
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            generate_audio: Flag to generate audio.
            sample_count: The number of video samples to generate.
            output_gcs_uri: GCS URL to store the final video.
            output_resolution: The resolution of the generated video.
            image2: The second optional reference image.
            image3: The third optional reference image.
            negative_prompt: An optional prompt to guide the model.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.
        """
        if image1 is None:
            raise APIInputError(
                "Image1 is required. At least reference image must be provided."
            )
        model_enum = Veo3Model[model]

        return utils.generate_video_from_references(
            client=self.client,
            model=model_enum,
            prompt=prompt,
            image1=image1,
            image2=image2,
            image3=image3,
            image_format=image_format,
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
            seed=seed,
        )

    def generate_video_from_gcsuri_image(
        self,
        model: str,
        gcsuri: str,
        image_format: str,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        generate_audio: bool,
        enhance_prompt: bool,
        sample_count: int,
        last_frame_gcsuri: str,
        output_gcs_uri: str,
        output_resolution: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from a Google Cloud Storage (GCS) image URI using the Veo 3.1 API.

        Args:
            model: Veo3 model.
            gcsuri: The GCS URI of the input image (e.g., "gs://my-bucket/path/to/image.jpg").
            image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
            prompt: The text prompt for video generation.
            compression_quality: Compression quality i.e optimized vs lossless.
            aspect_ratio: The desired aspect ratio of the video.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            last_frame_gcsuri: GCS URL of the last frame for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            output_resolution: The resolution of the generated video.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.

        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if gcsuri is None:
            raise APIInputError(
                "GCS URI for the image cannot be None for image-to-video generation."
            )
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            logger.warning(
                "Prompt is empty for image-to-video. Veo might use default interpretation of image."
            )
        if duration_seconds not in VEO3_VALID_DURATION_SECONDS:
            raise APIInputError(
                f"duration_seconds must be one of {VEO3_VALID_DURATION_SECONDS}, but got {duration_seconds}."
            )
        if sample_count not in VEO3_VALID_SAMPLE_COUNT:
            raise APIInputError(
                f"sample_count must be one of {VEO3_VALID_SAMPLE_COUNT} for Veo3, but got {sample_count}."
            )
        if aspect_ratio not in VEO3_VALID_ASPECT_RATIOS:
            raise APIInputError(
                f"Veo3 can only generate videos of aspect ratios {VEO3_VALID_ASPECT_RATIOS}. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise APIInputError(
                f"Veo3 can only generate videos of resolution {OUTPUT_RESOLUTION}. You passed aspect ratio {output_resolution}."
            )

        if last_frame_gcsuri:
            valid_bucket, validation_message = validate_gcs_uri_and_image(
                last_frame_gcsuri
            )
        valid_bucket, validation_message = utils.validate_gcs_uri_and_image(gcsuri)
        if not valid_bucket:
            # Re-raise as APIExecutionError if the failure is due to GCS API/resource lookup
            if (
                "not exist or is inaccessible" in validation_message
                or "resource not found" in validation_message
            ):
                raise APIExecutionError(validation_message)
            else:
                raise APIInputError(validation_message)
        logger.info(validation_message)

        input_image_format_upper = image_format.upper()
        mime_type: str
        if input_image_format_upper == "PNG":
            mime_type = "image/png"
        elif input_image_format_upper == "JPEG":
            mime_type = "image/jpeg"
        elif input_image_format_upper == "MP4":
            mime_type = "image/mp4"
        else:
            raise APIInputError(f"Unsupported image format: {image_format}")
        model = Veo3Model[model]
        return utils.generate_video_from_gcsuri_image(
            client=self.client,
            model=model,
            gcsuri=gcsuri,
            image_format=image_format,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            duration_seconds=duration_seconds,
            generate_audio=generate_audio,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            last_frame_gcsuri=last_frame_gcsuri,
            output_gcs_uri=output_gcs_uri,
            output_resolution=output_resolution,
            negative_prompt=negative_prompt,
            seed=seed,
        )
