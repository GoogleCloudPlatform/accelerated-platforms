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
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from .constants import MAX_SEED, SUPPORTED_VIDEO_EXTENSIONS, Veo3Model
from .veo_api import VeoAPI


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
                "aspect_ratio": (["16:9"], {"default": "16:9"}),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    [8],
                    {"default": 8},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        prompt: str = "A drone shot smoothly flies through an ancient, mist-shrouded jungle at dawn.",
        aspect_ratio: str = "16:9",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
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
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
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
                model=model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                generate_audio=generate_audio,
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
                "aspect_ratio": (["16:9"], {"default": "16:9"}),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    [8],
                    {"default": 8},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        gcsuri: str = "",
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
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
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
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
                model=model,
                gcsuri=gcsuri,
                image_format=image_format,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                person_generation=person_generation,
                duration_seconds=duration_seconds,
                generate_audio=generate_audio,
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
                "aspect_ratio": (["16:9"], {"default": "16:9"}),
                "person_generation": (
                    ["dont_allow", "allow_adult"],
                    {"default": "allow_adult"},
                ),
                "duration_seconds": (
                    [8],
                    {"default": 8},
                ),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "enhance_prompt": ("BOOLEAN", {"default": True}),
                "sample_count": ("INT", {"default": 1, "min": 1, "max": 2, "step": 1}),
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
    CATEGORY = "Google AI/Veo3"

    def generate(
        self,
        model: str = Veo3Model.VEO_3_PREVIEW.name,
        image: torch.Tensor = None,
        image_format: str = "PNG",
        prompt: str = "",
        aspect_ratio: str = "16:9",
        person_generation: str = "allow_adult",
        duration_seconds: int = 8,
        generate_audio: bool = True,
        enhance_prompt: bool = True,
        sample_count: int = 1,
        seed: Optional[int] = None,
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
            person_generation: Controls whether the model can generate people.
            duration_seconds: The desired duration of the video in seconds.
            generate_audio: Flag to generate audio.
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
                    model=model,
                    image=single_image_tensor,
                    image_format=image_format,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    person_generation=person_generation,
                    duration_seconds=duration_seconds,
                    generate_audio=generate_audio,
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


class Veo3VideoPreviewNode:
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

    CATEGORY = "Google AI/Veo3"

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


class Veo3SaveAndPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_paths": ("VEO_VIDEO",),
                "autoplay": ("BOOLEAN", {"default": True}),
                "mute": ("BOOLEAN", {"default": True}),
                "loop": ("BOOLEAN", {"default": False}),
                "save_video": ("BOOLEAN", {"default": False}),
                "save_video_file_prefix": ("STRING", {"default": "veo_video"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "preview_video"
    CATEGORY = "Google AI/Veo3"
    OUTPUT_NODE = True

    def preview_video(
        self, video_paths, autoplay, mute, loop, save_video, save_video_file_prefix
    ):
        try:
            # Destination directory for saving videos
            dest_dir = os.path.join("output", "veo")
            os.makedirs(dest_dir, exist_ok=True)
            # Setting preview dir to temp as the veo nodes save the video there
            preview_dir = "temp"
            os.makedirs(preview_dir, exist_ok=True)
            videos = []
            # Determine which input is provided
            for video_path in video_paths:
                if video_path and isinstance(video_path, str) and video_path.strip():
                    video_path = os.path.abspath(video_path)
                    if not os.path.exists(video_path):
                        raise FileNotFoundError(f"Video file not found: {video_path}")

                    ext = Path(video_path).suffix.lower()  # e.g., '.mp4', '.webm'
                    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
                        raise ValueError(
                            f"Unsupported video format: {ext}. Supported formats: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
                        )

                    video_file = os.path.basename(video_path)

                    if save_video:
                        # Generate unique filename with original extension
                        file_hash = hashlib.md5(
                            open(video_path, "rb").read()
                        ).hexdigest()[:8]
                        timestamp = int(time.time())
                        dest_name = f"{save_video_file_prefix}_{timestamp}_{file_hash}{ext}"  # Keeps original extension
                        dest_path = os.path.join(dest_dir, dest_name)

                        shutil.copy2(video_path, dest_path)
                        print(f"Video copied to: {dest_path}")
                else:
                    raise ValueError("'video_paths' must be provided.")
                video = [video_file, ""]
                videos.append(video)
            return {
                "ui": {
                    "video": videos,
                    "metadata": {
                        "width": 512,
                        "height": 512,
                        "autoplay": autoplay,
                        "mute": mute,
                        "loop": loop,
                    },
                }
            }

        except Exception as e:
            print(str(e))
            return {"ui": {"video": [], "error": str(e)}}


NODE_CLASS_MAPPINGS = {
    "Veo3TextToVideoNode": Veo3TextToVideoNode,
    "Veo3GcsUriImageToVideoNode": Veo3GcsUriImageToVideoNode,
    "Veo3ImageToVideoNode": Veo3ImageToVideoNode,
    "Veo3VideoPreviewNode": Veo3VideoPreviewNode,
    "Veo3SaveAndPreview": Veo3SaveAndPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Veo3TextToVideoNode": "Veo3 Text To Video",
    "Veo3GcsUriImageToVideoNode": "Veo3 Image To Video (GcsUriImage)",
    "Veo3ImageToVideoNode": "Veo3 Image To Video",
    "Veo3VideoPreviewNode": "Veo3 Video to VHS",
    "Veo3SaveAndPreview": "Veo3 preview and save video",
}
