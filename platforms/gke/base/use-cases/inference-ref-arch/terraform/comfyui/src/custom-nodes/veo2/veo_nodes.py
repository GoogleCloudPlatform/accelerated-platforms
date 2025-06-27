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
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

import cv2
import folder_paths
import numpy as np
import torch

from .constants import MAX_SEED
from .veo_api import VeoAPI


class VeoTextToVideoNode:
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
                    {"default": "dont_allow"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
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
        person_generation: str = "dont_allow",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
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
            api = VeoAPI(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            # Catch any exception from VeoAPI.__init__ (ValueError, RuntimeError)
            raise RuntimeError(f"Failed to initialize Veo API: {e}")

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


class VeoGcsUriImageToVideoNode:
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
                    ["PNG", "JPEG", "WEBP"],
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
                    {"default": "dont_allow"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
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
        person_generation: str = "dont_allow",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
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
            api = VeoAPI(project_id=gcp_project_id, region=gcp_region)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Veo API: {e}")

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


class VeoImageToVideoNode:
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
                    ["PNG", "JPEG", "WEBP"],
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
                    {"default": "dont_allow"},
                ),
                "duration_seconds": (
                    "INT",
                    {"default": 8, "min": 5, "max": 8, "step": 1},
                ),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
            },
            "optional": {
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
        person_generation: str = "dont_allow",
        duration_seconds: int = 8,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        seed: Optional[int] = None,
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
            compression_quality: Compression quality i.e optimized and lossless.
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            enhance_prompt: Whether to enhance the prompt automatically.
            sample_count: The number of video samples to generate.
            seed: An optional seed for reproducible video generation.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            gcp_project_id: GCP project ID where the Veo will be queried via Vertex AI APIs
            gcp_region: GCP region for Vertex AI APIs to query Veo

        Returns:
            A tuple containing a list of file paths to the generated videos.

        Raises:
            RuntimeError: If API initialization fails, or if video generation encounters an error.
        """
        try:
            api = VeoAPI(project_id=gcp_project_id, region=gcp_region)
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
                    image=single_image_tensor,
                    image_format=image_format,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    compression_quality=compression_quality,
                    person_generation=person_generation,
                    duration_seconds=duration_seconds,
                    enhance_prompt=enhance_prompt,
                    sample_count=sample_count,
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


class VideoPreviewNode:
    """
    A ComfyUI node for generating VHS compatible frames.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Defines the input types for the node.
        - video_paths: A list where each item is a path to a video file.
        """
        return {
            "required": {
                "video_paths": ("VEO_VIDEO",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("frames",)

    FUNCTION = "preview_videos"

    CATEGORY = "Google AI/Veo2"

    def preview_videos(self, video_paths: list[str]):
        """
        Loads multiple videos from newline-separated paths, extracts frames,
        and returns them as a single IMAGE batch.
        """
        all_preview_frames = []  # List to accumulate frames from ALL videos
        no_of_frames = 120
        if not video_paths:
            print("Error: No video paths provided.")
            dummy_image = torch.zeros(1, 512, 512, 3)
            return dummy_image

        print(f"Received {len(video_paths)} video path(s).")
        total_extracted_frames = 0
        try:
            for video_path in video_paths:
                print(f"--- Processing video: {video_path} ---")

                if not os.path.exists(video_path):
                    print(f"Error: Video file not found at '{video_path}'")
                    continue  # Skip to the next video

                if not os.path.isfile(video_path):
                    print(f"Error: Path '{video_path}' is not a file.")
                    continue  # Skip to the next video

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    print(f"Error: Could not open video file '{video_path}'")
                    continue

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames == 0:
                    print(f"Warning: Zero frames found in {video_path}")
                    continue

                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # Intelligent sampling , skipping directly to the frame instead of reading sequentially
                frame_step = max(1, total_frames // no_of_frames)
                frames_to_extract = min(no_of_frames, total_frames)

                # Extract frames
                for i in range(frames_to_extract):
                    frame_pos = min(i * frame_step, total_frames - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    ret, frame = cap.read()
                    if not ret:
                        break

                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    # Convert NumPy array to PyTorch Tensor
                    frame_tensor = torch.from_numpy(
                        frame_rgb.astype(np.float32) / 255.0
                    )

                    all_preview_frames.append(frame_tensor)
                cap.release()
                print(f"Finished processing '{video_path}'.")

        except Exception as e:
            print(f"An unexpected error occurred during frame extraction: {str(e)}")

        if all_preview_frames:
            final_output_frames = torch.stack(all_preview_frames, dim=0)

            return (final_output_frames,)
        else:
            print(
                "No frames were extracted from any video. Check paths or frame_interval."
            )
            return (dummy_image,)


NODE_CLASS_MAPPINGS = {
    "VeoTextToVideoNode": VeoTextToVideoNode,
    "VeoGcsUriImageToVideoNode": VeoGcsUriImageToVideoNode,
    "VeoImageToVideoNode": VeoImageToVideoNode,
    "VideoPreviewNode": VideoPreviewNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeoTextToVideoNode": "Veo2 Text To Video",
    "VeoGcsUriImageToVideoNode": "Veo2 Image To Video (GcsUriImage)",
    "VeoImageToVideoNode": "Veo2 Image To Video",
    "VideoPreviewNode": "Video to VHS",
}
