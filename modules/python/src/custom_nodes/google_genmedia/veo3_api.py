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

from . import exceptions, utils
from .base_api import GoogleGenAIBaseAPI
from .constants import OUTPUT_RESOLUTION, VEO3_MAX_VIDEOS, VEO3_USER_AGENT, Veo3Model


class Veo3API(GoogleGenAIBaseAPI):
    """
    A client for interacting with the Google Veo 3.0 API for video generation.
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
            exceptions.APIInitializationError: If GCP Project or Zone cannot be determined.
        """
        super().__init__(project_id, region, VEO3_USER_AGENT)

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
        Generates video from a text prompt using the Veo 3.0 API.

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
            exceptions.ConfigurationError: If input parameters are invalid (e.g., empty prompt, out-of-range duration/sample_count).
            exceptions.APICallError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            raise exceptions.ConfigurationError(
                "Prompt cannot be empty for text-to-video generation."
            )
        if duration_seconds != 8:
            raise exceptions.ConfigurationError(
                f"duration_seconds must be between 8 seconds for veo3, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= VEO3_MAX_VIDEOS):
            raise exceptions.ConfigurationError(
                f"sample_count must be between 1 and {VEO3_MAX_VIDEOS} for Veo3, but got {sample_count}."
            )
        if aspect_ratio != "16:9":
            raise exceptions.ConfigurationError(
                f"Veo3 can only generate videos of aspect ratio 16:9. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise exceptions.ConfigurationError(
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
        output_gcs_uri: str,
        output_resolution: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from an image input (as a torch.Tensor) using the Veo 3.0 API.

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
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            output_resolution: The resolution of the generated video.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.

        Raises:
            exceptions.ConfigurationError: If input parameters are invalid (e.g., empty prompt, unsupported image format, out-of-range duration/sample_count).
            exceptions.APICallError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            print(
                "Prompt is empty for image-to-video. Veo might use default interpretation of image."
            )

        if duration_seconds != 8:
            raise exceptions.ConfigurationError(
                f"duration_seconds must be between 8 seconds for veo3, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= VEO3_MAX_VIDEOS):
            raise exceptions.ConfigurationError(
                f"sample_count must be between 1 and {VEO3_MAX_VIDEOS} for Veo3, but got {sample_count}."
            )

        if image is None:
            raise exceptions.ConfigurationError(
                "Image input (torch.Tensor) cannot be None."
            )

        if aspect_ratio != "16:9":
            raise exceptions.ConfigurationError(
                f"Veo3 can only generate videos of aspect ratio 16:9. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise exceptions.ConfigurationError(
                f"Veo3 can only generate videos of resolution {OUTPUT_RESOLUTION}. You passed aspect ratio {output_resolution}."
            )
        last_frame = None  # this is because veo3 doesn't support last frame yet and both veo2 and veo3 share the same code base for making API calls.
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
        output_gcs_uri: str,
        output_resolution: str,
        negative_prompt: Optional[str],
        seed: Optional[int],
    ) -> List[str]:
        """
        Generates video from a Google Cloud Storage (GCS) image URI using the Veo 3.0 API.

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
            output_gcs_uri: output gcs url to store the video. Required with lossless output.
            output_resolution: The resolution of the generated video.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible video generation.

        Returns:
            A list of file paths to the generated videos.

        Raises:
            exceptions.ConfigurationError: If input parameters are invalid (e.g., empty prompt, unsupported image format,
                        invalid GCS URI, or if the GCS object is not a valid image).
            exceptions.APICallError: If video generation fails after retries, due to API errors, or unexpected issues.
        """
        if gcsuri is None:
            raise exceptions.ConfigurationError(
                "GCS URI for the image cannot be None for image-to-video generation."
            )
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            print(
                "Prompt is empty for image-to-video. Veo might use default interpretation of image."
            )

        if duration_seconds != 8:
            raise exceptions.ConfigurationError(
                f"duration_seconds must be between 8 seconds for veo3, but got {duration_seconds}."
            )
        if not (1 <= sample_count <= VEO3_MAX_VIDEOS):
            raise exceptions.ConfigurationError(
                f"sample_count must be between 1 and {VEO3_MAX_VIDEOS}, but got {sample_count}."
            )
        if aspect_ratio != "16:9":
            raise exceptions.ConfigurationError(
                f"Veo3 can only generate videos of aspect ratio 16:9. You passed aspect ratio {aspect_ratio}."
            )
        if output_resolution not in OUTPUT_RESOLUTION:
            raise exceptions.ConfigurationError(
                f"Veo3 can only generate videos of resolution {OUTPUT_RESOLUTION}. You passed aspect ratio {output_resolution}."
            )

        valid_bucket, validation_message = utils.validate_gcs_uri_and_image(gcsuri)
        if valid_bucket:
            print(validation_message)
        else:
            raise exceptions.ConfigurationError(validation_message)

        if not image_format:
            raise exceptions.ConfigurationError("Image format cannot be empty.")
        input_image_format_upper = image_format.upper()
        mime_type: str
        if input_image_format_upper == "PNG":
            mime_type = "image/png"
        elif input_image_format_upper == "JPEG":
            mime_type = "image/jpeg"
        elif input_image_format_upper == "MP4":
            mime_type = "image/mp4"
        else:
            raise exceptions.ConfigurationError(
                f"Unsupported image format: {image_format}"
            )
        last_frame_gcsuri = None  # this is because veo3 doesn't support last frame yet and both veo2 and veo3 share the same code base for making API calls.
        model = Veo3Model[model]
        return utils.generate_video_from_gcsuri_image(
            client=self.client,
            model=model,
            gcsuri=gcsuri,
            image_format=mime_type,
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
