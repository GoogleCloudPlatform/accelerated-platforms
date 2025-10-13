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

import base64
import functools  # Added for decorator
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

from .constants import STORAGE_USER_AGENT
from .custom_exceptions import APIExecutionError, APIInputError
from .retry import api_error_retry


def base64_to_pil_to_tensor(base64_string: str) -> torch.Tensor:
    """
    Decodes a base64 string and converts the resulting image to a PyTorch tensor.

    Args:
        base64_string: The base64 encoded string of an image.

    Returns:
        A PyTorch tensor of the image, formatted as (1, height, width, channels)
        with float values in the [0, 1] range.
    """
    image_data = base64.b64decode(base64_string)
    pil_image = PIL_Image.open(io.BytesIO(image_data)).convert("RGBA")
    image_array = np.array(pil_image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(image_array)[None,]

    return tensor


def download_gcsuri(gcsuri: str, destination: str) -> bool:
    """
    Downloads a file from a Google Cloud Storage (GCS) URI to a specified local destination path.

    This function validates the GCS URI format, extracts the bucket and blob names,
    and then attempts to download the GCS object.

    Args:
        gcsuri: The Google Cloud Storage URI of the video file to download (e.g., "gs://your-bucket/path/to/file.mp4").
        destination: The full local file path where the downloaded GCS object will be saved.

    Returns:
        bool: True if the download was successful.

    Raises:
        APIInputError: If the provided `gcsuri` is not in a valid GCS URI format.
        APIExecutionError: If an error occurs during the GCS download operation.
    """

    if not gcsuri.startswith("gs://"):
        raise APIInputError("Invalid GCS URI format. Must start with 'gs://'")

    path_parts = gcsuri[len("gs://") :].split("/", 1)
    if len(path_parts) < 2:
        raise APIInputError("Invalid GCS URI: No object path specified.")

    bucket_name = path_parts[0]
    blob_name = path_parts[1]

    try:
        storage_client = storage.Client(
            client_info=ClientInfo(user_agent=STORAGE_USER_AGENT)
        )
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Download the blob to the specified local file path
        blob.download_to_filename(destination)
        print(f"Successfully downloaded '{gcsuri}' to '{destination}'")
        return True

    except api_core_exceptions.GoogleAPICallError as e:
        # Handle specific GCS API errors (like Not Found, Permission Denied)
        if e.code == StatusCode.NOT_FOUND:
            raise APIExecutionError(
                f"GCS object not found at '{gcsuri}'. Error: {e.details}"
            ) from e
        elif e.code in (StatusCode.PERMISSION_DENIED, StatusCode.UNAUTHENTICATED):
            raise APIExecutionError(
                f"Permission denied to access GCS resource at '{gcsuri}'. Error: {e.details}"
            ) from e
        else:
            raise APIExecutionError(
                f"GCS API error during download of '{gcsuri}': {e.details}"
            ) from e
    except Exception as e:
        # Catch any other unexpected non-API specific errors.
        raise APIExecutionError(
            f"An unexpected error occurred during GCS download of '{gcsuri}': {e}"
        ) from e


@api_error_retry
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
) -> List[PIL_Image.Image]:
    """
    Generate image from text prompt using Imagen.

    Args:
        client: genai.Client
        model: model to be used
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

    Returns:
        A list of PIL Image objects. Returns an empty list on failure.

    Raises:
        APIInputError: If input parameters are invalid (e.g., unsupported output type).
        APIExecutionError: If the API call fails due to quota, permissions, or server issues.
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

    print("Sending request to Imagen API for text-to-image generation...")
    response = client.models.generate_images(model=model, prompt=prompt, config=config)

    if not response.generated_images:
        error_message = "Image generation failed or was blocked by safety filters."
        raise APIExecutionError(error_message)

    generated_pil_images: List[PIL_Image.Image] = []
    for i, generated_image in enumerate(response.generated_images):
        if generated_image.image:
            image_bytes = generated_image.image.image_bytes
            pil_image = PIL_Image.open(BytesIO(image_bytes))
            generated_pil_images.append(pil_image)
        elif generated_image.error:
            print(f"Error generating image {i+1}: {generated_image.error}")

    return generated_pil_images


@api_error_retry
def generate_video_from_gcsuri_image(
    client: genai.Client,
    model: str,
    gcsuri: str,
    image_format: str,
    prompt: str,
    aspect_ratio: str,
    output_resolution: Optional[str],
    compression_quality: Optional[str],
    person_generation: str,
    duration_seconds: int,
    generate_audio: Optional[bool],
    enhance_prompt: bool,
    sample_count: int,
    last_frame_gcsuri: Optional[str],
    output_gcs_uri: Optional[str],
    negative_prompt: Optional[str],
    seed: Optional[int],
) -> List[str]:
    """
    Generates video from a Google Cloud Storage (GCS) image URI using the Veo API.

    Args:
        client: genai.Client
        model: model to be used
        gcsuri: The GCS URI of the input image (e.g., "gs://my-bucket/path/to/image.jpg").
        image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video.
        output_resolution: The resolution of the generated video.
        compression_quality: Compression quality i.e optimized vs lossless.
        person_generation: Controls whether the model can generate people.
        duration_seconds: The desired duration of the video in seconds.
        generate_audio: Flag to generate audio. Only allowed in Veo3.
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
        APIExecutionError: If video generation fails due to API or unexpected issues.
    """
    if compression_quality == "lossless" and not output_gcs_uri:
        raise APIInputError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise APIInputError(f"Incorrect compression_quality type {compression_quality}")

    temp_config = {
        "aspect_ratio": aspect_ratio,
        "person_generation": person_generation,
        "compression_quality": compression_quality_type,
        "duration_seconds": duration_seconds,
        "enhance_prompt": enhance_prompt,
        "number_of_videos": sample_count,
        "negative_prompt": negative_prompt,
        "seed": seed,
    }

    if output_gcs_uri:
        valid_bucket, validation_message = validate_gcs_uri_and_image(
            output_gcs_uri, False
        )
        if valid_bucket:
            print(validation_message)
        else:
            if (
                "not exist or is inaccessible" in validation_message
                or "resource not found" in validation_message
            ):
                raise APIExecutionError(validation_message)
            else:
                raise APIInputError(validation_message)
        temp_config["output_gcs_uri"] = output_gcs_uri

    if re.search(
        r"veo-3\.0",
        model.value if isinstance(model, object) and hasattr(model, "value") else model,
    ):
        if generate_audio:
            temp_config["generate_audio"] = generate_audio
        else:
            temp_config["generate_audio"] = False
        temp_config["resolution"] = output_resolution

    if re.search(
        r"veo-2\.0",
        model.value if isinstance(model, object) and hasattr(model, "value") else model,
    ):
        if last_frame_gcsuri:
            temp_config["last_frame"] = Image(
                gcs_uri=last_frame_gcsuri, mime_type=image_format
            )

    config = GenerateVideosConfig(**temp_config)
    print(f"Config for image-to-video generation: {config}")

    print("Sending request to Veo API for image-to-video generation")
    operation = client.models.generate_videos(
        model=model,
        image=Image(gcs_uri=gcsuri, mime_type=image_format),
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

    return process_video_response(operation)


@api_error_retry
def generate_video_from_image(
    client: genai.Client,
    model: str,
    image: torch.Tensor,
    image_format: str,
    prompt: str,
    aspect_ratio: str,
    output_resolution: Optional[str],
    compression_quality: Optional[str],
    person_generation: str,
    duration_seconds: int,
    generate_audio: Optional[bool],
    enhance_prompt: bool,
    sample_count: int,
    last_frame: torch.Tensor,
    output_gcs_uri: Optional[str],
    negative_prompt: Optional[str],
    seed: Optional[int],
) -> List[str]:
    """
    Generates video from an image input (as a torch.Tensor) using the Veo API.

    Args:
        client: genai.Client
        model: model to be used
        image: The input image as a torch.Tensor (ComfyUI format).
        image_format: The format of the input image (e.g., "PNG", "JPEG", "MP4").
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video.
        output_resolution: The resolution of the generated video.
        compression_quality: Compression quality i.e optimized vs lossless.
        person_generation: Controls whether the model can generate people.
        duration_seconds: The desired duration of the video in seconds.
        generate_audio: Flag to generate audio. Only allowed in Veo3.
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
        APIExecutionError: If video generation fails due to API or unexpected issues.
    """
    input_image_format_upper = image_format.upper()
    mime_type: str

    if input_image_format_upper == "PNG":
        mime_type = "image/png"
    elif input_image_format_upper == "JPEG":
        mime_type = "image/jpeg"
    elif input_image_format_upper == "MP4":
        mime_type = "image/mp4"
    else:
        raise APIInputError(
            f"Unsupported image format for Base64 encoding: {image_format}"
        )

    veo_image_input_str = tensor_to_pil_to_base64(image, input_image_format_upper)
    if not veo_image_input_str:
        raise APIExecutionError(
            "Failed to prepare image input bytes for Veo API. Bytes are empty."
        )

    if compression_quality == "lossless" and not output_gcs_uri:
        raise APIInputError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise APIInputError(f"Incorrect compression_quality type {compression_quality}")

    temp_config = {
        "aspect_ratio": aspect_ratio,
        "person_generation": person_generation,
        "compression_quality": compression_quality_type,
        "duration_seconds": duration_seconds,
        "enhance_prompt": enhance_prompt,
        "number_of_videos": sample_count,
        "negative_prompt": negative_prompt,
        "seed": seed,
    }

    if output_gcs_uri:
        valid_bucket, validation_message = validate_gcs_uri_and_image(
            output_gcs_uri, False
        )
        if valid_bucket:
            print(validation_message)
        else:
            if (
                "not exist or is inaccessible" in validation_message
                or "resource not found" in validation_message
            ):
                raise APIExecutionError(validation_message)
            else:
                raise APIInputError(validation_message)
        temp_config["output_gcs_uri"] = output_gcs_uri

    if re.search(
        r"veo-3\.0",
        model.value if isinstance(model, object) and hasattr(model, "value") else model,
    ):
        if generate_audio:
            temp_config["generate_audio"] = generate_audio
        else:
            temp_config["generate_audio"] = False
        temp_config["resolution"] = output_resolution

    if re.search(
        r"veo-2\.0",
        model.value if isinstance(model, object) and hasattr(model, "value") else model,
    ):
        if last_frame is not None:
            last_frame_str = tensor_to_pil_to_base64(
                last_frame, input_image_format_upper
            )
            temp_config["last_frame"] = Image(
                image_bytes=last_frame_str, mime_type=mime_type
            )

    config = GenerateVideosConfig(**temp_config)
    print(f"Config for image-to-video generation: {config}")

    print(
        f"Sending request to Veo API for image-to-video generation with prompt: '{prompt[:80]}...'"
    )

    operation = client.models.generate_videos(
        model=model,
        image=Image(image_bytes=veo_image_input_str, mime_type=mime_type),
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
    return process_video_response(operation)


@api_error_retry
def generate_video_from_text(
    client: genai.Client,
    model: str,
    prompt: str,
    aspect_ratio: str,
    output_resolution: Optional[str],
    compression_quality: Optional[str],
    person_generation: str,
    duration_seconds: int,
    generate_audio: Optional[bool],
    enhance_prompt: bool,
    sample_count: int,
    output_gcs_uri: Optional[str],
    negative_prompt: Optional[str],
    seed: Optional[int],
) -> List[str]:
    """
    Generates video from a text prompt using the Veo API.

    Args:
        client: genai.Client
        model: model to be used
        prompt: The text prompt for video generation.
        aspect_ratio: The desired aspect ratio of the video (e.g., "16:9", "1:1").
        output_resolution: The resolution of the generated video.
        compression_quality: Compression quality i.e optimized vs lossless.
        person_generation: Controls whether the model can generate people ("allow" or "dont_allow").
        duration_seconds: The desired duration of the video in seconds.
        generate_audio: Flag to generate audio. Only allowed in Veo3.
        enhance_prompt: Whether to enhance the prompt automatically.
        sample_count: The number of video samples to generate.
        output_gcs_uri: output gcs url to store the video. Required with lossless output.
        negative_prompt: An optional prompt to guide the model to avoid generating certain things.
        seed: An optional seed for reproducible video generation.

    Returns:
        A list of file paths to the generated videos.

    Raises:
        APIInputError: If input parameters are invalid (e.g., empty prompt, out-of-range duration/sample_count).
        APIExecutionError: If video generation fails after retries, due to API errors, or unexpected issues.
    """
    if compression_quality == "lossless" and not output_gcs_uri:
        raise APIInputError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise APIInputError(f"Incorrect compression_quality type {compression_quality}")

    temp_config = {
        "aspect_ratio": aspect_ratio,
        "person_generation": person_generation,
        "compression_quality": compression_quality_type,
        "duration_seconds": duration_seconds,
        "enhance_prompt": enhance_prompt,
        "number_of_videos": sample_count,
        "negative_prompt": negative_prompt,
        "seed": seed,
    }

    if output_gcs_uri:
        valid_bucket, validation_message = validate_gcs_uri_and_image(
            output_gcs_uri, False
        )
        if valid_bucket:
            print(validation_message)
        else:
            if (
                "not exist or is inaccessible" in validation_message
                or "resource not found" in validation_message
            ):
                raise APIExecutionError(validation_message)
            else:
                raise APIInputError(validation_message)
        temp_config["output_gcs_uri"] = output_gcs_uri

    if re.search(
        r"veo-3\.0",
        model.value if isinstance(model, object) and hasattr(model, "value") else model,
    ):
        if generate_audio:
            temp_config["generate_audio"] = generate_audio
        else:
            temp_config["generate_audio"] = False
        temp_config["resolution"] = output_resolution

    config = GenerateVideosConfig(**temp_config)
    print(f"Config for text-to-video generation: {config}")

    print("Sending request to Veo API for text-to-video generation...")
    operation = client.models.generate_videos(model=model, prompt=prompt, config=config)
    print(f"Initial operation response object type: {type(operation)}")

    operation_count = 0
    while not operation.done:
        time.sleep(20)  # Polling interval
        operation = client.operations.get(operation)
        operation_count += 1
        print(f"Polling operation (attempt {operation_count})...")

    print(f"Operation completed with status: {operation.done}")
    return process_video_response(operation)


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
        APIInputError: If the specified `file_path` does not exist.
        APIExecutionError: If an error occurs during the file reading or conversion process.
    """
    if not os.path.exists(file_path):
        raise APIInputError(f"Media file not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            media_bytes = f.read()
        print(f"Read the file {file_path}")
        return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
    except Exception as e:
        # Pass the original exception up, but with more context
        raise APIExecutionError(
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
        APIExecutionError: If no video data is found in the API response or if saving fails.
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
        raise APIExecutionError(error_msg)

    print(f"Found {len(videos_data)} videos to process.")
    for n, video_item in enumerate(videos_data):
        timestamp = int(time.time())
        unique_id = random.randint(1000, 99999)
        video_filename = f"veo_{timestamp}_{unique_id}_{n}.mp4"
        video_path = os.path.join(output_dir, video_filename)
        try:
            if (
                hasattr(video_item, "video")
                and hasattr(video_item.video, "save")
                and not (hasattr(video_item.video, "uri") and video_item.video.uri)
            ):
                video_item.video.save(video_path)
                video_paths.append(video_path)
                print(f"Saved video {n} using video_item.video.save() to {video_path}")
            elif (
                hasattr(video_item, "video")
                and hasattr(video_item.video, "uri")
                and video_item.video.uri
            ):
                if download_gcsuri(video_item.video.uri, video_path):
                    video_paths.append(video_path)
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
            # We catch all here as download_gcsuri already raises an APIExecutionError.
            if isinstance(e, APIExecutionError):
                raise
            print(f"Error saving video {n} to {video_path}: {e}")

    if not video_paths:
        raise APIExecutionError(
            "Failed to save any videos despite successful generation response."
        )

    print(f"Successfully processed and saved {len(video_paths)} videos.")
    return video_paths


def validate_gcs_uri_and_image(
    gcs_uri: str, check_object: bool = True
) -> Tuple[bool, str]:
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
        # Exit with True status if the check was only for the GCS URI and not the object.
        if not check_object:
            return (True, f"GCS URI is valid.")
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
        # Map GoogleAPICallError for GCS checks to a generic failure message
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


def tensor_to_pil_to_base64(image: torch.tensor, format="PNG") -> bytes:
    """Converts a PyTorch tensor or PIL Image into PNG-encoded bytes.

    This function processes an input image, which can be either a PyTorch tensor
    or a PIL Image object. If the input is a tensor, it is first converted to a
    PIL Image. The function then saves the final PIL Image as a PNG into an
    in-memory buffer and returns its raw byte content.

    Args:
        image (torch.Tensor | PIL.Image.Image): The input image. If it's a
            PyTorch tensor, it is expected to have a shape like (1, H, W, C)
            and float values in the [0, 1] range.

    Returns:
        bytes: The raw bytes of the image, encoded in PNG format.
    """

    pil_image: PIL_Image.Image
    image_input_bytes: bytes
    try:
        if isinstance(image, torch.Tensor):
            image_np = (image.squeeze(0).cpu().numpy() * 255).astype(np.uint8)
            pil_image = PIL_Image.fromarray(image_np)
            print("Converted input image tensor to PIL Image for Base64 encoding.")
        else:
            pil_image = image
            print(f"Using input image as is for Base64 (type: {type(image)}).")

        buffered = io.BytesIO()
        pil_image.save(buffered, format=format)
        image_input_bytes = buffered.getvalue()
        image_base64 = base64.b64encode(image_input_bytes).decode("utf-8")
        return image_base64
    except Exception as e:
        print(f"Cant convert the image to base64 {e}")
        print(f"Cant convert the image to base64 {e}")
