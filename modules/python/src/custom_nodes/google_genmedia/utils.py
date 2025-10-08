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

from . import exceptions
from .constants import STORAGE_USER_AGENT
from .retry import retry_on_api_error


def base64_to_pil_to_tensor(base64_string: str) -> torch.Tensor:
    try:
        image_data = base64.b64decode(base64_string)
        pil_image = PIL_Image.open(io.BytesIO(image_data)).convert("RGBA")
        image_array = np.array(pil_image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(image_array)[
            None,
        ]
        return tensor
    except Exception as e:
        raise exceptions.FileProcessingError(
            f"Failed to decode and convert base64 image: {e}"
        )


def download_gcsuri(gcsuri: str, destination: str) -> bool:
    if not gcsuri.startswith("gs://"):
        raise exceptions.ConfigurationError(
            "Invalid GCS URI format returned by Veo. Must start with 'gs://'"
        )

    path_parts = gcsuri[len("gs://") :].split("/", 1)
    if len(path_parts) < 2:
        raise exceptions.ConfigurationError(
            "Invalid GCS URI: No object path specified in the URL returned by Veo."
        )

    bucket_name = path_parts[0]
    blob_name = path_parts[1]

    try:
        storage_client = storage.Client(
            client_info=ClientInfo(user_agent=STORAGE_USER_AGENT)
        )
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(destination)
        print(f"Successfully downloaded '{gcsuri}' to '{destination}'")
        return True

    except Exception as e:
        raise exceptions.FileProcessingError(f"Error downloading '{gcsuri}': {e}")


@retry_on_api_error()
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

    generated_pil_images: List[PIL_Image.Image] = []
    print("Sending request to Imagen API for text-to-image generation...")

    response = client.models.generate_images(model=model, prompt=prompt, config=config)

    if not response.generated_images:
        error_message = "Image generation failed or was blocked by safety filters."
        raise exceptions.APICallError(error_message)

    for i, generated_image in enumerate(response.generated_images):
        if generated_image.image:
            image_bytes = generated_image.image.image_bytes
            pil_image = PIL_Image.open(BytesIO(image_bytes))
            generated_pil_images.append(pil_image)
        elif generated_image.error:
            print(f"Error generating image {i+1}: {generated_image.error}")

    return generated_pil_images


@retry_on_api_error()
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
    if compression_quality == "lossless" and not output_gcs_uri:
        raise exceptions.ConfigurationError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise exceptions.ConfigurationError(
            f"Incorrect compression_quality type {compression_quality}"
        )

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
        validate_gcs_uri_and_image(output_gcs_uri, False)
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
    print("Sending request to Veo API for image-to-video generation")

    operation = client.models.generate_videos(
        model=model,
        image=Image(gcs_uri=gcsuri, mime_type=image_format),
        prompt=prompt,
        config=config,
    )

    operation_count = 0
    while not operation.done:
        time.sleep(20)
        try:
            operation = client.operations.get(operation)
        except genai_errors.ClientError as e:
            error_message = "A client error occurred while polling. Please check the Project ID and region."
            print(f"{error_message} Original error: {e.message}")
            raise exceptions.APICallError(error_message) from e
        except Exception as e:
            print(
                f"An unexpected error occurred while polling for video generation status: {e}"
            )
            raise exceptions.APICallError(
                f"Polling for video generation status failed: {e}"
            ) from e
        operation_count += 1
        print(f"Polling operation (attempt {operation_count})...")

    print(f"Operation completed with status: {operation.done}")
    return process_video_response(operation)


@retry_on_api_error()
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
            f"Unsupported image format for Base64 encoding: {image_format}"
        )

    veo_image_input_str = tensor_to_pil_to_base64(image, input_image_format_upper)
    if not veo_image_input_str:
        raise exceptions.FileProcessingError(
            "Failed to prepare image input bytes for Veo API. Bytes are empty."
        )

    if compression_quality == "lossless" and not output_gcs_uri:
        raise exceptions.ConfigurationError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise exceptions.ConfigurationError(
            f"Incorrect compression_quality type {compression_quality}"
        )

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
        validate_gcs_uri_and_image(output_gcs_uri, False)
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
    print(
        f"Sending request to Veo API for image-to-video generation with prompt: '{prompt[:80]}...'"
    )
    operation = client.models.generate_videos(
        model=model,
        image=Image(image_bytes=veo_image_input_str, mime_type=mime_type),
        prompt=prompt,
        config=config,
    )
    operation_count = 0
    while not operation.done:
        time.sleep(20)
        try:
            operation = client.operations.get(operation)
        except genai_errors.ClientError as e:
            error_message = "A client error occurred while polling. Please check the Project ID and region."
            print(f"{error_message} Original error: {e.message}")
            raise exceptions.APICallError(error_message) from e
        except Exception as e:
            print(
                f"An unexpected error occurred while polling for video generation status: {e}"
            )
            raise exceptions.APICallError(
                f"Polling for video generation status failed: {e}"
            ) from e
        operation_count += 1
        print(f"Polling operation (attempt {operation_count})...")

    print(f"Operation completed with status: {operation.done}")
    return process_video_response(operation)


@retry_on_api_error()
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
    if compression_quality == "lossless" and not output_gcs_uri:
        raise exceptions.ConfigurationError(
            "output_gcs_uri must be passed for lossless video generation."
        )

    if compression_quality == "lossless":
        compression_quality_type = types.VideoCompressionQuality.LOSSLESS
    elif compression_quality == "optimized":
        compression_quality_type = types.VideoCompressionQuality.OPTIMIZED
    else:
        raise exceptions.ConfigurationError(
            f"Incorrect compression_quality type {compression_quality}"
        )

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
        validate_gcs_uri_and_image(output_gcs_uri, False)
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
    print("Sending request to Veo API for text-to-video generation...")
    operation = client.models.generate_videos(model=model, prompt=prompt, config=config)
    operation_count = 0
    while not operation.done:
        time.sleep(20)  # Polling interval
        try:
            operation = client.operations.get(operation)
        except genai_errors.ClientError as e:
            error_message = "A client error occurred while polling. Please check the Project ID and region."
            print(f"{error_message} Original error: {e.message}")
            raise exceptions.APICallError(error_message) from e
        except Exception as e:
            print(
                f"An unexpected error occurred while polling for video generation status: {e}"
            )
            raise exceptions.APICallError(
                f"Polling for video generation status failed: {e}"
            ) from e
        operation_count += 1
        print(f"Polling operation (attempt {operation_count})...")

    print(f"Operation completed with status: {operation.done}")
    return process_video_response(operation)


def media_file_to_genai_part(file_path: str, mime_type: str) -> types.Part:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            media_bytes = f.read()
        print(f"Read the file {file_path}")
        return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
    except Exception as e:
        raise exceptions.FileProcessingError(
            f"Error converting media file {file_path} (MIME: {mime_type}) to genai.types.Part: {e}"
        )


def prep_for_media_conversion(file_path: str, mime_type: str) -> Optional[types.Part]:
    if os.path.exists(file_path):
        print(f"Attempting to load media from: {file_path}")
        try:
            return media_file_to_genai_part(file_path, mime_type)
        except Exception as e:
            print(f"Warning: Could not add media file {file_path}: {e}")
            return None
    else:
        print(f"The file path {file_path} does not exist. Skipping.")
        return None


def process_video_response(operation: Any) -> List[str]:
    output_dir = folder_paths.get_temp_directory()
    os.makedirs(output_dir, exist_ok=True)

    video_paths: List[str] = []
    videos_data: List[Any] = []

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
        raise exceptions.APICallError(error_msg)

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
            print(f"Error saving video {n} to {video_path}: {e}")

    if not video_paths:
        raise exceptions.APICallError(
            "Failed to save any videos despite successful generation response."
        )

    print(f"Successfully processed and saved {len(video_paths)} videos.")
    return video_paths


@retry_on_api_error()
def validate_gcs_uri_and_image(gcs_uri: str, check_object: bool = True) -> None:
    GCS_URI_PATTERN = re.compile(
        r"^gs://(?P<bucket>[a-z0-9][a-z0-9._-]{1,61}[a-z0-9])(?:/(?P<object_path>.*))?$"
    )
    match = GCS_URI_PATTERN.match(gcs_uri)
    if not match:
        raise exceptions.ConfigurationError(
            f"Invalid GCS URI format: '{gcs_uri}'. Does not match 'gs://bucket/object' pattern."
        )

    bucket_name = match.group("bucket")
    object_path = match.group("object_path")

    storage_client = storage.Client(
        client_info=ClientInfo(user_agent=STORAGE_USER_AGENT)
    )
    bucket = storage_client.bucket(bucket_name)

    if not bucket.exists():
        raise exceptions.ConfigurationError(
            f"GCS bucket '{bucket_name}' does not exist or is inaccessible."
        )

    if not check_object:
        return  # Bucket exists, we are done.

    if not object_path:
        raise exceptions.ConfigurationError(
            f"GCS URI '{gcs_uri}' points to a bucket, but an object path is required."
        )

    blob = bucket.blob(object_path)
    if not blob.exists():
        raise exceptions.ConfigurationError(
            f"GCS object '{object_path}' not found in bucket '{bucket_name}'."
        )


def tensor_to_pil_to_base64(image: torch.tensor, format="PNG") -> bytes:
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
        raise exceptions.FileProcessingError(
            f"Failed to convert tensor to base64 image: {e}"
        )
