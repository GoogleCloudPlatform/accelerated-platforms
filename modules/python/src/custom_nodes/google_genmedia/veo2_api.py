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

from typing import List, Optional

import torch
from google import genai

from . import utils
from .base import VertexAIClient
from .constants import (
    VEO2_GENERATE_AUDIO_FLAG,
    VEO2_MODEL_ID,
    VEO2_OUTPUT_RESOLUTION,
    VEO2_USER_AGENT,
)
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .logger import get_node_logger
from .utils import validate_gcs_uri_and_image

logger = get_node_logger(__name__)


class Veo2API(VertexAIClient):
    """
    A client for interacting with the Google Veo 2.0 API for video generation.
    """

    def __init__(
        self, project_id: Optional[str] = None, region: Optional[str] = None
    ) -> None:
        """
        Initializes the Veo2API client.

        Args:
            project_id: The GCP project ID. If None, it will be retrieved from GCP metadata.
            region: The GCP region. If None, it will be retrieved from GCP metadata.

        Raises:
            ConfigurationError: If GCP Project or region cannot be determined or client initialization fails.
        """
        super().__init__(
            gcp_project_id=project_id, gcp_region=region, user_agent=VEO2_USER_AGENT
        )

    def generate_video_from_text(
        self,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        enhance_prompt: bool,
        sample_count: int,
        output_gcs_uri: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from a text prompt using the Veo 2.0 API.

        Args:
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video (e.g., "16:9", "1:1").
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people ("allow" or "dont_allow").
            duration_seconds: The desired duration of the video in seconds (5-8 seconds).
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate (1-4).
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
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
        if not (5 <= duration_seconds <= 8):
            raise APIInputError(
                f"duration_seconds must be between 5 and 8, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= 4):
            raise APIInputError(
                f"sample_count must be between 1 and 4, but got {sample_count}."
            )
        return utils.generate_video_from_text(
            client=self.client,
            model=VEO2_MODEL_ID,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            duration_seconds=duration_seconds,
            generate_audio=VEO2_GENERATE_AUDIO_FLAG,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            output_gcs_uri=output_gcs_uri,
            output_resolution=VEO2_OUTPUT_RESOLUTION,
            negative_prompt=negative_prompt,
            seed=seed,
        )

    def generate_video_from_image(
        self,
        image: torch.Tensor,
        image_format: str,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        enhance_prompt: bool,
        sample_count: int,
        last_frame: torch.Tensor,
        output_gcs_uri: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from an image input (as a torch.Tensor) using the Veo 2.0 API.

        Args:
            image: The input image as a torch.Tensor (ComfyUI format).
            image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            last_frame: last frame for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
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

        if not (1 <= duration_seconds <= 8):
            raise APIInputError(
                f"duration_seconds must be between 1 and 8, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= 4):
            raise APIInputError(
                f"sample_count must be between 1 and 4, but got {sample_count}."
            )

        if image is None:
            raise APIInputError("Image input (torch.Tensor) cannot be None.")

        return utils.generate_video_from_image(
            client=self.client,
            model=VEO2_MODEL_ID,
            image=image,
            image_format=image_format,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            generate_audio=VEO2_GENERATE_AUDIO_FLAG,
            duration_seconds=duration_seconds,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            last_frame=last_frame,
            output_gcs_uri=output_gcs_uri,
            output_resolution=VEO2_OUTPUT_RESOLUTION,
            negative_prompt=negative_prompt,
            seed=seed,
        )

    def generate_video_from_gcsuri_image(
        self,
        gcsuri: str,
        image_format: str,
        prompt: str,
        aspect_ratio: str,
        compression_quality: str,
        person_generation: str,
        duration_seconds: int,
        enhance_prompt: bool,
        sample_count: int,
        last_frame_gcsuri: str,
        output_gcs_uri: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from a Google Cloud Storage (GCS) image URI using the Veo 2.0 API.

        Args:
            gcsuri: The GCS URI of the input image (e.g., "gs://my-bucket/path/to/image.jpg").
            image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
            prompt: The text prompt for video generation.
            aspect_ratio: The desired aspect ratio of the video.
            compression_quality: Compression quality i.e optimized vs lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            last_frame_gcsuri: gcsuri of the last frame image for interpolation.
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
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

        if not (1 <= duration_seconds <= 8):
            raise APIInputError(
                f"duration_seconds must be between 1 and 8, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= 4):
            raise APIInputError(
                f"sample_count must be between 1 and 4, but got {sample_count}."
            )

        valid_bucket, validation_message = validate_gcs_uri_and_image(gcsuri)
        if valid_bucket:
            logger.info(f"gcsuri of the input image is valid {validation_message}")
        else:
            # Re-raise as APIExecutionError if the failure is due to GCS API/resource lookup
            if (
                "not exist or is inaccessible" in validation_message
                or "resource not found" in validation_message
            ):
                raise APIExecutionError(
                    f"gcsuri of the input image is not valid {validation_message}"
                )
            else:
                raise APIInputError(
                    f"gcsuri of the input image is not valid {validation_message}"
                )

        if last_frame_gcsuri:
            valid_bucket, validation_message = validate_gcs_uri_and_image(
                last_frame_gcsuri
            )
            if valid_bucket:
                logger.info(f"last frame gcsuri is valid {validation_message}")
            else:
                # Re-raise as APIExecutionError if the failure is due to GCS API/resource lookup
                if (
                    "not exist or is inaccessible" in validation_message
                    or "resource not found" in validation_message
                ):
                    raise APIExecutionError(
                        f"last frame gcs uri is not valid {validation_message}"
                    )
                else:
                    raise APIInputError(
                        f"last frame gcs uri is not valid {validation_message}"
                    )

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

        return utils.generate_video_from_gcsuri_image(
            client=self.client,
            model=VEO2_MODEL_ID,
            gcsuri=gcsuri,
            image_format=mime_type,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            compression_quality=compression_quality,
            person_generation=person_generation,
            duration_seconds=duration_seconds,
            generate_audio=VEO2_GENERATE_AUDIO_FLAG,
            enhance_prompt=enhance_prompt,
            sample_count=sample_count,
            last_frame_gcsuri=last_frame_gcsuri,
            output_gcs_uri=output_gcs_uri,
            output_resolution=VEO2_OUTPUT_RESOLUTION,
            negative_prompt=negative_prompt,
            seed=seed,
        )
