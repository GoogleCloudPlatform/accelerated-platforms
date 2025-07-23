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

import io
import mimetypes
import os
import random
import re
import time
from io import BytesIO
from typing import Any, List, Optional, Tuple

import folder_paths
import numpy as np
import torch
from google import genai
from google.api_core import exceptions as api_core_exceptions
from google.api_core.client_info import ClientInfo
from google.cloud import storage
from google.genai import errors as genai_errors
from google.genai import types
from google.genai.types import GenerateVideosConfig, Image
from grpc import StatusCode
from PIL import Image as PIL_Image

from .config import get_gcp_metadata
from .constants import STORAGE_USER_AGENT


def generate_image_from_text(
    client: genai.Client,
    model: str,
    prompt: str,
    person_generation: str,
    aspect_ratio: str,
    number_of_images: int,
    negative_prompt: str,
    seed: Optional[int],
    enhance_prompt: bool,
    add_watermark: bool,
    output_image_type: str,
    safety_filter_level: str,
    retry_count: int,
    retry_delay: int,
) -> List[PIL_Image.Image]:
    """
    Generate image from text prompt using Imagen3.

    Args:
        client: genai.Client
        mode: model to be used
        prompt: The text prompt for image generation.
        person_generation: Controls whether the model can generate people.
        aspect_ratio: The desired aspect ratio of the images.
        number_of_images: The number of images to generate (1-4).
        negative_prompt: A prompt to guide the model to avoid generating certain things.
        seed: Optional. A seed for reproducible image generation.
        enhance_prompt: Whether to enhance the prompt automatically.
        add_watermark: Whether to add a watermark to the generated images.
        output_image_type: The desired output image format (PNG or JPEG).
        safety_filter_level: The safety filter strictness.
        retry_count: number of retries
        retry_delay: time between each retry_count

    Returns:
        A list of PIL Image objects. Returns an empty list on failure.

    Raises:
        ValueError: If `number_of_images` is not between 1 and 4,
                    if `seed` is provided with `add_watermark` enabled,
                    or if `output_image_type` is unsupported.
    """
    config = types.GenerateImagesConfig(
        number_of_images=number_of_images,
        aspect_ratio=aspect_ratio,
        person_generation=person_generation,
        negative_prompt=negative_prompt,
        seed=seed,
        enhance_prompt=enhance_prompt,
        add_watermark=add_watermark,
        output_mime_type=output_image_type,
        safety_filter_level=safety_filter_level,
    )

    retries = 0
    generated_pil_images: List[PIL_Image.Image] = []
    while retries <= retry_count:
        try:
            print("Sending request to Imagen API for text-to-image generation...")
            response = client.models.generate_images(
                model=model, prompt=prompt, config=config
            )

            if not response.generated_images:
                error_message = (
                    "Image generation failed or was blocked by safety filters."
                )
                raise RuntimeError(error_message)

            for i, generated_image in enumerate(response.generated_images):
                if generated_image.image:
                    image_bytes = generated_image.image.image_bytes
                    pil_image = PIL_Image.open(BytesIO(image_bytes))
                    generated_pil_images.append(pil_image)
                elif generated_image.error:
                    print(f"Error generating image {i+1}: {generated_image.error}")

            return generated_pil_images
        except genai_errors.ClientError as e:
            if e.code == StatusCode.RESOURCE_EXHAUSTED:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Quota/Resource Exhausted (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Quota/Resource Exhausted after {retries} attempts for {model} (Code: {e.code.name}). "
                    )
            elif e.code == StatusCode.INVALID_ARGUMENT:
                raise ValueError(
                    f"Invalid API argument supplied. Check your prompt and parameters. Error: {e.details}"
                )
            elif (
                e.code == StatusCode.PERMISSION_DENIED
                or e.code == StatusCode.UNAUTHENTICATED
                or e.code == StatusCode.FORBIDDEN
            ):
                raise RuntimeError(
                    f"Permission denied. Check your GCP service account permissions for Veo API. Error: {e.details}"
                )
            else:
                # Catch any other ClientError that's not specifically handled (e.g., Bad Request, Conflict)
                raise RuntimeError(
                    f"Unexpected Veo API Client Error (Code: {e.code.name}). Error: {e.details}"
                )

        except genai_errors.ServerError as e:
            if e.code == StatusCode.UNAVAILABLE:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Service Unavailable (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Service Unavailable after {retries} attempts. Giving up. Last error: {e.details}"
                    )
            elif e.code == StatusCode.DEADLINE_EXCEEDED:
                raise RuntimeError(
                    f"API request timed out (Deadline Exceeded). Error: {e.details}"
                )
            else:
                # Catch any other ServerError types
                raise RuntimeError(
                    f"Unexpected Veo API Server Error (Code: {e.code.name}). Error: {e.details}"
                )

    return []


def generate_video_from_gcsuri_image(
    client: genai.Client,
    model: str,
    gcsuri: str,
    image_format: str,
    prompt: str,
    aspect_ratio: str,
    person_generation: str,
    duration_seconds: int,
    enhance_prompt: bool,
    sample_count: int,
    negative_prompt: Optional[str],
    seed: Optional[int],
    retry_count: int,
    retry_delay: int,
) -> List[str]:
    """
    Generates video from a Google Cloud Storage (GCS) image URI using the Veo 2 API.

    Args:
        client: genai.Client
        model: model to be used
        gcsuri: The GCS URI of the input image (e.g., "gs://my-bucket/path/to/image.jpg").
        image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video.
        person_generation: Controls whether the model can generate people.
        duration_seconds: The desired duration of the video in seconds.
        enhance_prompt: Whether to enhance the prompt automatically.
        sample_count: The number of video samples to generate.
        negative_prompt: An optional prompt to guide the model to avoid generating certain things.
        seed: An optional seed for reproducible video generation.
        retry_count: number of retries
        retry_delay: time between each retry_count

    Returns:
        A list of file paths to the generated videos.

    Raises:
        ValueError: If input parameters are invalid (e.g., empty prompt, unsupported image format,
                        invalid GCS URI, or if the GCS object is not a valid image).
        RuntimeError: If video generation fails after retries, due to API errors, or unexpected issues.
    """
    valid_bucket, validation_message = validate_gcs_uri_and_image(gcsuri)
    if valid_bucket:
        print(validation_message)
    else:
        raise ValueError(validation_message)

    input_image_format_upper = image_format.upper()
    mime_type: str
    if input_image_format_upper == "PNG":
        mime_type = "image/png"
    elif input_image_format_upper == "JPEG":
        mime_type = "image/jpeg"
    elif input_image_format_upper == "MP4":
        mime_type = "image/mp4"
    else:
        raise ValueError(f"Unsupported image format: {image_format}")

    config = GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        person_generation=person_generation,
        duration_seconds=duration_seconds,
        enhance_prompt=enhance_prompt,
        number_of_videos=sample_count,
        negative_prompt=negative_prompt,
        seed=seed,
    )

    retries = 0
    while retries <= retry_count:
        try:
            print("Sending request to Veo API for image-to-video generation")
            operation = client.models.generate_videos(
                model=model,
                image=Image(gcs_uri=gcsuri, mime_type=mime_type),
                prompt=prompt,
                config=config,
            )
            print(f"Initial operation response object type: {type(operation)}")

            operation_count = 0
            while not operation.done:
                time.sleep(20)
                operation = client.operations.get(operation)
                operation_count += 1
                print(f"Polling operation (attempt {operation_count})...")

            print(f"Operation completed with status: {operation.done}")

            # return self._process_video_response(operation)
            return process_video_response(operation)
        except genai_errors.ClientError as e:
            if e.code == StatusCode.RESOURCE_EXHAUSTED:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Quota/Resource Exhausted (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Quota/Resource Exhausted after {retries} attempts for {model} (Code: {e.code.name}). "
                    )
            elif e.code == StatusCode.INVALID_ARGUMENT:
                raise ValueError(
                    f"Invalid API argument supplied. Check your prompt and parameters. Error: {e.details}"
                )
            elif (
                e.code == StatusCode.PERMISSION_DENIED
                or e.code == StatusCode.UNAUTHENTICATED
                or e.code == StatusCode.FORBIDDEN
            ):
                raise RuntimeError(
                    f"Permission denied. Check your GCP service account permissions for Veo API. Error: {e.details}"
                )
            else:
                # Catch any other ClientError that's not specifically handled (e.g., Bad Request, Conflict)
                raise RuntimeError(
                    f"Unexpected Veo API Client Error (Code: {e.code.name}). Error: {e.details}"
                )

        except genai_errors.ServerError as e:
            if e.code == StatusCode.UNAVAILABLE:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Service Unavailable (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Service Unavailable after {retries} attempts. Giving up. Last error: {e.details}"
                    )
            elif e.code == StatusCode.DEADLINE_EXCEEDED:
                raise RuntimeError(
                    f"API request timed out (Deadline Exceeded). Error: {e.details}"
                )
            else:
                # Catch any other ServerError types
                raise RuntimeError(
                    f"Unexpected Veo API Server Error (Code: {e.code.name}). Error: {e.details}"
                )

        except Exception as e:
            # Catch any other unexpected non-API specific errors.
            raise RuntimeError(
                f"An unexpected non-API error occurred during video generation: {e}"
            )


def generate_video_from_image(
    client: genai.Client,
    model: str,
    image: torch.Tensor,
    image_format: str,
    prompt: str,
    aspect_ratio: str,
    person_generation: str,
    duration_seconds: int,
    enhance_prompt: bool,
    sample_count: int,
    negative_prompt: Optional[str],
    seed: Optional[int],
    retry_count: int,
    retry_delay: int,
) -> List[str]:
    """
    Generates video from an image input (as a torch.Tensor) using the Veo 2 API.

    Args:
        client: genai.Client
        model: model to be used
        image: The input image as a torch.Tensor (ComfyUI format).
        image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video.
        person_generation: Controls whether the model can generate people.
        duration_seconds: The desired duration of the video in seconds.
        enhance_prompt: Whether to enhance the prompt automatically.
        sample_count: The number of video samples to generate.
        negative_prompt: An optional prompt to guide the model to avoid generating certain things.
        seed: An optional seed for reproducible video generation.
        retry_count: number of retries
        retry_delay: time between each retry_count

    Returns:
        A list of file paths to the generated videos.

    Raises:
        ValueError: If input parameters are invalid (e.g., empty prompt, unsupported image format, out-of-range duration/sample_count).
        RuntimeError: If video generation fails after retries, due to API errors, or unexpected issues.
    """
    pil_image: PIL_Image.Image
    if isinstance(image, torch.Tensor):
        image_np = (image.squeeze(0).cpu().numpy() * 255).astype(np.uint8)
        pil_image = PIL_Image.fromarray(image_np)
        print("Converted input image tensor to PIL Image for Base64 encoding.")
    else:
        pil_image = image
        print(f"Using input image as is for Base64 (type: {type(image)}).")

    veo_image_input_bytes: bytes
    input_image_format_upper = image_format.upper()
    mime_type: str

    if input_image_format_upper == "PNG":
        mime_type = "image/png"
    elif input_image_format_upper == "JPEG":
        mime_type = "image/jpeg"
    elif input_image_format_upper == "MP4":
        mime_type = "image/mp4"
    else:
        raise ValueError(
            f"Unsupported image format for Base64 encoding: {image_format}"
        )

    buffered = io.BytesIO()
    pil_image.save(buffered, format=input_image_format_upper)
    veo_image_input_bytes = buffered.getvalue()
    print("Prepared image as BytesIO.")

    if not veo_image_input_bytes:
        raise RuntimeError(
            "Failed to prepare image input bytes for Veo API. Bytes are empty."
        )

    config = GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        person_generation=person_generation,
        duration_seconds=duration_seconds,
        enhance_prompt=enhance_prompt,
        number_of_videos=sample_count,
        negative_prompt=negative_prompt,
        seed=seed,
    )

    retries = 0
    while retries <= retry_count:
        try:
            print(
                f"Sending request to Veo API for image-to-video generation with prompt: '{prompt[:80]}...'"
            )

            operation = client.models.generate_videos(
                model=model,
                image=Image(image_bytes=veo_image_input_bytes, mime_type=mime_type),
                prompt=prompt,
                config=config,
            )
            print(f"Initial operation response object type: {type(operation)}")

            operation_count = 0
            while not operation.done:
                time.sleep(20)
                operation = client.operations.get(operation)
                operation_count += 1
                print(f"Polling operation (attempt {operation_count})...")

            print(f"Operation completed with status: {operation.done}")

            # return _process_video_response(operation)
            return process_video_response(operation)
        except genai_errors.ClientError as e:
            if e.code == StatusCode.RESOURCE_EXHAUSTED:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Quota/Resource Exhausted (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Quota/Resource Exhausted after {retries} attempts for {model} (Code: {e.code.name}). "
                    )
            elif e.code == StatusCode.INVALID_ARGUMENT:
                raise ValueError(
                    f"Invalid API argument supplied. Check your prompt and parameters. Error: {e.details}"
                )
            elif (
                e.code == StatusCode.PERMISSION_DENIED
                or e.code == StatusCode.UNAUTHENTICATED
                or e.code == StatusCode.FORBIDDEN
            ):
                raise RuntimeError(
                    f"Permission denied. Check your GCP service account permissions for Veo API. Error: {e.details}"
                )
            else:
                # Catch any other ClientError that's not specifically handled (e.g., Bad Request, Conflict)
                raise RuntimeError(
                    f"Unexpected Veo API Client Error (Code: {e.code.name}). Error: {e.details}"
                )

        except genai_errors.ServerError as e:
            if e.code == StatusCode.UNAVAILABLE:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Service Unavailable (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Service Unavailable after {retries} attempts. Giving up. Last error: {e.details}"
                    )
            elif e.code == StatusCode.DEADLINE_EXCEEDED:
                raise RuntimeError(
                    f"API request timed out (Deadline Exceeded). Error: {e.details}"
                )
            else:
                # Catch any other ServerError types
                raise RuntimeError(
                    f"Unexpected Veo API Server Error (Code: {e.code.name}). Error: {e.details}"
                )

        except Exception as e:
            # Catch any other unexpected non-API specific errors.
            raise RuntimeError(
                f"An unexpected non-API error occurred during video generation: {e}"
            )
    raise RuntimeError("Video generation failed with an unknown error path.")


def generate_video_from_text(
    client: genai.Client,
    model: str,
    prompt: str,
    aspect_ratio: str,
    person_generation: str,
    duration_seconds: int,
    enhance_prompt: bool,
    sample_count: int,
    negative_prompt: Optional[str],
    seed: Optional[int],
    retry_count: int,
    retry_delay: int,
) -> List[str]:
    """
    Generates video from a text prompt using the Veo API.

    Args:
        client: genai.Client
        model: model to be used
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video (e.g., "16:9", "1:1").
        person_generation: Controls whether the model can generate people ("allow" or "dont_allow").
        duration_seconds: The desired duration of the video in seconds.
        enhance_prompt: Whether to enhance the prompt automatically.
        sample_count: The number of video samples to generate.
        negative_prompt: An optional prompt to guide the model to avoid generating certain things.
        seed: An optional seed for reproducible video generation.
        retry_count: number of retries
        retry_delay: time between each retry_count

    Returns:
        A list of file paths to the generated videos.

    Raises:
        ValueError: If input parameters are invalid (e.g., empty prompt, out-of-range duration/sample_count).
        RuntimeError: If video generation fails after retries, due to API errors, or unexpected issues.
    """
    config = GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        person_generation=person_generation,
        duration_seconds=duration_seconds,
        enhance_prompt=enhance_prompt,
        number_of_videos=sample_count,
        negative_prompt=negative_prompt,
        seed=seed,
    )
    print(f"Config for text-to-video generation: {config}")

    retries = 0
    while retries <= retry_count:
        try:
            print("Sending request to Veo API for text-to-video generation...")
            operation = client.models.generate_videos(
                model=model, prompt=prompt, config=config
            )
            print(f"Initial operation response object type: {type(operation)}")

            operation_count = 0
            while not operation.done:
                time.sleep(20)  # Polling interval
                operation = client.operations.get(operation)
                operation_count += 1
                print(f"Polling operation (attempt {operation_count})...")

            print(f"Operation completed with status: {operation.done}")

            # Process the response, will raise RuntimeError if no videos found
            # return self._process_video_response(operation)
            return process_video_response(operation)

        except genai_errors.ClientError as e:
            if e.code == StatusCode.RESOURCE_EXHAUSTED:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Quota/Resource Exhausted (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Quota/Resource Exhausted after {retries} attempts for {model} (Code: {e.code.name}). "
                    )
            elif e.code == StatusCode.INVALID_ARGUMENT:
                raise ValueError(
                    f"Invalid API argument supplied. Check your prompt and parameters. Error: {e.details}"
                )
            elif (
                e.code == StatusCode.PERMISSION_DENIED
                or e.code == StatusCode.UNAUTHENTICATED
                or e.code == StatusCode.FORBIDDEN
            ):
                raise RuntimeError(
                    f"Permission denied. Check your GCP service account permissions for Veo API. Error: {e.details}"
                )
            else:
                # Catch any other ClientError that's not specifically handled (e.g., Bad Request, Conflict)
                raise RuntimeError(
                    f"Unexpected Veo API Client Error (Code: {e.code.name}). Error: {e.details}"
                )

        except genai_errors.ServerError as e:
            if e.code == StatusCode.UNAVAILABLE:
                retries += 1
                if retries <= retry_count:
                    retry_wait = retry_delay
                    print(
                        f"API Service Unavailable (attempt {retries}/{retry_count}) - "
                        f"Code: {e.code.name}. Waiting {retry_wait:.1f} seconds before retry. Error: {e.details}"
                    )
                    time.sleep(retry_wait)
                else:
                    raise RuntimeError(
                        f"API Service Unavailable after {retries} attempts. Giving up. Last error: {e.details}"
                    )
            elif e.code == StatusCode.DEADLINE_EXCEEDED:
                raise RuntimeError(
                    f"API request timed out (Deadline Exceeded). Error: {e.details}"
                )
            else:
                # Catch any other ServerError types
                raise RuntimeError(
                    f"Unexpected Veo API Server Error (Code: {e.code.name}). Error: {e.details}"
                )

        except Exception as e:
            # Catch any other unexpected non-API specific errors.
            raise RuntimeError(
                f"An unexpected non-API error occurred during video generation: {e}"
            )


def media_file_to_genai_part(file_path: str, mime_type: str) -> types.Part:
    """Reads a media file (image, audio, or video) and converts it to a genai.types.Part.

    This function is designed to prepare the raw bytes of a media file for input to
    the Gemini API. It reads the file in binary mode and encapsulates the content
    along with its specified MIME type into a `genai.types.Part` object.

    Args:
        file_path (str): The absolute or relative path to the media file.
        mime_type (str): The MIME type of the media file (e.g., 'image/png', 'audio/wav', 'video/mp4').

    Returns:
        types.Part: A `genai.types.Part` object containing the media file's bytes
                    and MIME type, ready for API input.

    Raises:
        FileNotFoundError: If the specified `file_path` does not exist.
        IOError: If an error occurs during the file reading or conversion process.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            media_bytes = f.read()
        print(f"Read the file {file_path}")
        return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
    except Exception as e:
        # Pass the original exception up, but with more context
        raise IOError(
            f"Error converting media file {file_path} (MIME: {mime_type}) to genai.types.Part: {e}"
        )


def prep_for_media_conversion(file_path: str, mime_type: str) -> Optional[types.Part]:
    """Attempts to prepare a media file into a genai.types.Part for input to the model.

    This function checks if the specified file exists and, if so, attempts to convert it
    into a format suitable for the `genai` model. It handles potential errors during
    the conversion process.

    Args:
        file_path (str): The absolute or relative path to the media file.
        mime_type (str): The MIME type of the media file (e.g., 'image/jpeg', 'video/mp4').

    Returns:
        Optional[types.Part]: A `genai.types.Part` object if the file is successfully
                              loaded and converted, otherwise `None`.
    """
    if os.path.exists(file_path):
        print(f"Attempting to load media from: {file_path}")
        try:
            return media_file_to_genai_part(file_path, mime_type)
        except Exception as e:
            print(f"Warning: Could not add media file {file_path}: {e}")
            return None  # Return None on failure
    else:
        print(f"The file path {file_path} does not exist. Skipping.")
        return None  # Return None if file not found


def process_video_response(operation: Any) -> List[str]:
    """
    Processes the video generation operation response and saves generated videos.

    Args:
        operation: The completed LRO (Long Running Operation) object from the Veo API.

    Returns:
        A list of file paths to the saved video files.

    Raises:
        RuntimeError: If no video data is found in the API response or if saving fails.
    """
    # store the output in temp directory. The video will be previewed using Preview custom node custom node and saved in output dir if needed
    output_dir = folder_paths.get_temp_directory()
    os.makedirs(output_dir, exist_ok=True)

    video_paths: List[str] = []
    videos_data: List[Any] = []

    # Define a list of possible paths to 'generated_videos' within the operation response
    possible_paths = [
        lambda op: getattr(op.response, "generated_videos", None),
        lambda op: getattr(op.result, "generated_videos", None),
        lambda op: (
            op.response.get("generated_videos")
            if isinstance(op.response, dict)
            else None
        ),
        lambda op: (
            op.response.get("generateVideoResponse", {}).get("generated_videos")
            if isinstance(op.response, dict)
            else None
        ),
        lambda op: (
            [op.response.get("generateVideoResponse")]
            if isinstance(op.response, dict)
            and isinstance(op.response.get("generateVideoResponse"), dict)
            else None
        ),
        lambda op: op.response if isinstance(op.response, list) else None,
        lambda op: [op.response] if hasattr(op.response, "video") else None,
        lambda op: [op.result] if hasattr(op.result, "video") else None,
    ]

    for get_data_func in possible_paths:
        try:
            temp_data = get_data_func(operation)
            if temp_data is not None:
                if isinstance(temp_data, list) and temp_data:
                    videos_data = temp_data
                    print(
                        f"Found videos data via path: {getattr(get_data_func, '__qualname__', 'lambda')}"
                    )
                    break
                elif hasattr(temp_data, "video"):
                    videos_data = [temp_data]
                    print(
                        f"Found single video object via path: {getattr(get_data_func, '__qualname__', 'lambda')}"
                    )
                    break
        except AttributeError:
            pass
        except Exception as e:
            print(
                f"Error trying video data extraction path ({getattr(get_data_func, '__qualname__', 'lambda')}): {e}"
            )

    if not videos_data:
        error_msg = (
            "No video data found in the API response after trying all known structures. "
            "This might indicate an unexpected API response format or a failed generation without explicit error."
        )
        print(error_msg)
        print(f"Full operation object at time of video extraction failure: {operation}")
        raise RuntimeError(error_msg)

    print(f"Found {len(videos_data)} videos to process.")

    for n, video_item in enumerate(videos_data):
        timestamp = int(time.time())
        unique_id = random.randint(1000, 99999)
        video_filename = f"veo_{timestamp}_{unique_id}_{n}.mp4"
        video_path = os.path.join(output_dir, video_filename)

        try:
            if hasattr(video_item, "video") and hasattr(video_item.video, "save"):
                video_item.video.save(video_path)
                video_paths.append(video_path)
                print(f"Saved video {n} using video_item.video.save() to {video_path}")
            elif hasattr(video_item, "video_bytes"):
                with open(video_path, "wb") as f:
                    f.write(video_item.video_bytes)
                video_paths.append(video_path)
                print(f"Saved video {n} using video_item.video_bytes to {video_path}")
            else:
                print(
                    f"Video {n} could not be saved: Neither 'video.save()' nor 'video_bytes' found on video_item. "
                    f"Skipping this video. Item type: {type(video_item)}"
                )
                print(f"Problematic video item structure for video {n}: {video_item}")

        except Exception as e:
            print(f"Error saving video {n} to {video_path}: {e}")

    if not video_paths:
        raise RuntimeError(
            "Failed to save any videos despite successful generation response."
        )

    print(f"Successfully processed and saved {len(video_paths)} videos.")
    return video_paths


def validate_gcs_uri_and_image(gcs_uri: str) -> Tuple[bool, str]:
    """
    Validates if a given string is a valid GCS URI and if the object it points to
    exists and is identified as an image.

    Args:
        gcs_uri: The Google Cloud Storage URI (e.g., "gs://my-bucket/path/to/image.jpg").

    Returns:
        A tuple where the first element is True if valid and an image,
        False otherwise. The second element is a message indicating
        the validation status or error.
    """
    GCS_URI_PATTERN = re.compile(
        r"^gs://(?P<bucket>[a-z0-9][a-z0-9._-]{1,61}[a-z0-9])(?:/(?P<object_path>.*))?$"
    )
    match = GCS_URI_PATTERN.match(gcs_uri)
    if not match:
        return (
            False,
            f"Invalid GCS URI format: '{gcs_uri}'. Does not match 'gs://bucket/object' pattern.",
        )

    bucket_name = match.group("bucket")
    object_path = match.group("object_path")

    try:
        storage_client = storage.Client(
            client_info=ClientInfo(user_agent=STORAGE_USER_AGENT)
        )
        bucket = storage_client.bucket(bucket_name)

        if not bucket.exists():
            return (
                False,
                f"GCS bucket '{bucket_name}' does not exist or is inaccessible.",
            )

        blob = bucket.blob(object_path)

        if not blob.exists():
            return (
                False,
                f"GCS object '{object_path}' not found in bucket '{bucket_name}'.",
            )

        blob.reload()
        content_type = blob.content_type
        if content_type is None:
            inferred_type, _ = mimetypes.guess_type(object_path)
            if inferred_type:
                content_type = inferred_type
            else:
                return (
                    False,
                    f"GCS object '{object_path}' has no content type set and cannot be inferred as an image.",
                )

        if not content_type.startswith("image/"):
            return (
                False,
                f"GCS object '{object_path}' is not an image. Content-Type: {content_type}",
            )

        return (
            True,
            f"GCS URI is valid and object '{object_path}' is a valid image (Content-Type: {content_type}).",
        )

    except api_core_exceptions.GoogleAPICallError as e:
        if e.code == StatusCode.NOT_FOUND:
            return False, f"GCS resource not found: {e.details}"
        elif (
            e.code == StatusCode.PERMISSION_DENIED
            or e.code == StatusCode.UNAUTHENTICATED
        ):
            return (
                False,
                f"Permission denied to access GCS resource: {e.details}. Check your credentials and bucket/object permissions.",
            )
        else:
            return (
                False,
                f"An unexpected GCS API error occurred: {e.details} (Code: {e.code.name})",
            )
    except Exception as e:
        return False, f"An unexpected error occurred during GCS validation: {e}"
