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

# This is a preview version of Google GenAI custom nodes

import hashlib
import mimetypes
import os
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from moviepy import VideoFileClip

from .constants import SUPPORTED_VIDEO_EXTENSIONS
from .custom_exceptions import APIInputError, ConfigurationError
from .logger import get_node_logger

logger = get_node_logger(__name__)


class VeoVideoToVHSNode:
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

    FUNCTION = "convert_videos"

    CATEGORY = "Google AI/Utils"

    def convert_videos(self, video_paths: list[str]):
        """
        Loads multiple videos from newline-separated paths, extracts frames,
        and returns them as a single IMAGE batch.
        """
        all_preview_frames = []  # List to accumulate frames from ALL videos
        no_of_frames = 120
        if not video_paths:
            logger.error("No video paths provided.")
            dummy_image = torch.zeros(1, 512, 512, 3)
            return dummy_image

        logger.info(f"Received {len(video_paths)} video path(s).")
        total_extracted_frames = 0
        try:
            for video_path in video_paths:
                logger.info(f"Processing video: {video_path}")

                if not os.path.exists(video_path):
                    logger.error(f"Video file not found at '{video_path}'")
                    continue  # Skip to the next video

                if not os.path.isfile(video_path):
                    logger.error(f"Path '{video_path}' is not a file.")
                    continue  # Skip to the next video

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    logger.error(f"Could not open video file '{video_path}'")
                    continue

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames == 0:
                    logger.warning(f"Zero frames found in {video_path}")
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
                logger.info(f"Finished processing '{video_path}'.")

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during frame extraction: {str(e)}"
            )

        if all_preview_frames:
            final_output_frames = torch.stack(all_preview_frames, dim=0)

            return (final_output_frames,)
        else:
            logger.warning(
                "No frames were extracted from any video. Check paths or frame_interval."
            )
            return (dummy_image,)


class VeoVideoSaveAndPreview:
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
    CATEGORY = "Google AI/Utils"
    OUTPUT_NODE = True

    def preview_video(
        self, video_paths, autoplay, mute, loop, save_video, save_video_file_prefix
    ):
        try:
            dest_dir = os.path.join("output", "veo")
            os.makedirs(dest_dir, exist_ok=True)

            # Setting preview dir to temp as the veo nodes save the video there
            # ComfyUI's 'temp' directory is usually handled by its file system backend
            preview_dir = "temp"
            os.makedirs(preview_dir, exist_ok=True)  # Ensure temp directory exists

            videos_output_for_ui = (
                []
            )  # This will hold data for both your JS widget and ComfyUI's queue

            # Determine which input is provided
            for video_path in video_paths:
                if video_path and isinstance(video_path, str) and video_path.strip():
                    video_path_abs = os.path.abspath(
                        video_path
                    )  # Use absolute path for moviepy

                    if not os.path.exists(video_path_abs):
                        raise APIInputError(f"Video file not found: {video_path_abs}")

                    ext = Path(video_path_abs).suffix.lower()
                    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
                        raise APIInputError(
                            f"Unsupported video format: {ext}. Supported formats: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
                        )

                    video_file_basename = os.path.basename(video_path_abs)
                    video_subfolder = (
                        ""  # ComfyUI expects a subfolder, often empty for 'temp'
                    )
                    duration = 0.0
                    width = 0
                    height = 0
                    video_format = ""

                    try:
                        with VideoFileClip(video_path_abs) as clip:
                            duration = clip.duration
                            width, height = clip.size
                            # Guess MIME type from extension
                            mime_type, _ = mimetypes.guess_type(video_file_basename)
                            video_format = (
                                mime_type
                                if mime_type and mime_type.startswith("video/")
                                else "video/mp4"
                            )
                    except Exception as moviepy_e:
                        logger.warning(
                            f"Could not get video metadata for {video_file_basename} using moviepy: {moviepy_e}"
                        )
                        # Fallback for format if moviepy fails. In this case the default will not be mp4 since moviepy failed to process it.
                        mime_type, _ = mimetypes.guess_type(video_file_basename)
                        video_format = (
                            mime_type
                            if mime_type and mime_type.startswith("video/")
                            else "video/unknown"
                        )

                    if save_video:
                        file_hash = hashlib.md5(
                            open(video_path_abs, "rb").read()
                        ).hexdigest()[:8]
                        timestamp = int(time.time())
                        dest_name = (
                            f"{save_video_file_prefix}_{timestamp}_{file_hash}{ext}"
                        )
                        dest_path = os.path.join(dest_dir, dest_name)

                        shutil.copy2(video_path_abs, dest_path)
                        logger.info(f"Video copied to: {dest_path}")
                        video_subfolder = "veo"
                    else:
                        # if it is just for preview, strip the filename and build the path starting temp directory
                        dest_path = os.path.join(
                            os.path.normpath("temp"),
                            os.path.normpath(video_path_abs)
                            .rsplit(os.path.normpath("temp"), 1)[1]
                            .lstrip(os.path.sep),
                        )
                    video_item_for_ui = {
                        "filename": dest_path,
                        "subfolder": video_subfolder,  # This should be "" if not saved, or "veo" if saved
                        "type": (
                            "output" if save_video else "temp"
                        ),  # 'output' for saved, 'temp' for preview only
                        "duration": duration,
                        "width": width,
                        "height": height,
                        "format": video_format,
                    }
                    videos_output_for_ui.append(video_item_for_ui)
                else:
                    raise APIInputError("'video_paths' must be provided and not empty.")

            return {
                "ui": {
                    "video": videos_output_for_ui,
                    "metadata": {
                        "width": (
                            videos_output_for_ui[0]["width"]
                            if videos_output_for_ui
                            else 0
                        ),
                        "height": (
                            videos_output_for_ui[0]["height"]
                            if videos_output_for_ui
                            else 0
                        ),
                        "autoplay": autoplay,
                        "mute": mute,
                        "loop": loop,
                    },
                }
            }

        except (APIInputError, ConfigurationError) as e:
            logger.error(f"An error occurred in VeoVideoSaveAndPreview: {str(e)}")
            return {"ui": {"video": [], "error": str(e)}}
        except Exception as e:
            logger.error(
                f"An unexpected error occurred in VeoVideoSaveAndPreview: {str(e)}"
            )
            return {"ui": {"video": [], "error": str(e)}}


NODE_CLASS_MAPPINGS = {
    "VeoVideoToVHSNode": VeoVideoToVHSNode,
    "VeoVideoSaveAndPreview": VeoVideoSaveAndPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeoVideoToVHSNode": "Video to VHS",
    "VeoVideoSaveAndPreview": "Preview/Save video",
}
