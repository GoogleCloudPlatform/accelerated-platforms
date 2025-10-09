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
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import torch
from moviepy import VideoFileClip

from .constants import SUPPORTED_VIDEO_EXTENSIONS
from .custom_exceptions import APIExecutionError, APIInputError


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

    def convert_videos(self, video_paths: List[str]) -> Tuple[torch.Tensor,]:
        """
        Loads multiple videos from newline-separated paths, extracts frames,
        and returns them as a single IMAGE batch.

        Args:
            video_paths: A list of file paths to the video files.

        Returns:
            A tuple containing a PyTorch tensor of the extracted frames.

        Raises:
            RuntimeError: If video processing fails or no frames are extracted.
        """
        all_preview_frames = []  # List to accumulate frames from ALL videos
        no_of_frames = 120
        dummy_image = torch.zeros(1, 512, 512, 3)

        if not video_paths:
            raise RuntimeError("No video paths provided for frame extraction.")

        print(f"Received {len(video_paths)} video path(s).")
        try:
            for video_path in video_paths:
                print(f"--- Processing video: {video_path} ---")

                if not os.path.exists(video_path):
                    raise APIInputError(f"Video file not found at '{video_path}'")

                if not os.path.isfile(video_path):
                    raise APIInputError(f"Path '{video_path}' is not a file.")

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    raise APIExecutionError(
                        f"Could not open video file '{video_path}' for reading."
                    )

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames == 0:
                    print(f"Warning: Zero frames found in {video_path}. Skipping.")
                    cap.release()
                    continue

                # width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) # Unused variable
                # height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) # Unused variable

                # Intelligent sampling , skipping directly to the frame instead of reading sequentially
                frames_to_extract = min(no_of_frames, total_frames)
                frame_step = max(1, total_frames // frames_to_extract)

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
                print(
                    f"Finished processing '{video_path}'. Extracted {len(all_preview_frames)} frames so far."
                )

        except APIInputError as e:
            raise RuntimeError(f"Video to VHS Input Error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"Video to VHS Execution Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during frame extraction: {str(e)}"
            ) from e

        if all_preview_frames:
            final_output_frames = torch.stack(all_preview_frames, dim=0)
            return (final_output_frames,)
        else:
            raise RuntimeError(
                "No frames were extracted from any video. Check video paths or contents."
            )


class VeoVideoSaveAndPreview:
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
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
        self,
        video_paths: List[str],
        autoplay: bool,
        mute: bool,
        loop: bool,
        save_video: bool,
        save_video_file_prefix: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Prepares video data for display in the ComfyUI front-end and optionally saves the video
        to the output directory.

        Args:
            video_paths: List of local paths to the video files (usually in the /temp directory).
            autoplay: Whether the video should autoplay in the UI.
            mute: Whether the video should be muted in the UI.
            loop: Whether the video should loop in the UI.
            save_video: Whether to save the video to the /output directory.
            save_video_file_prefix: Prefix for the saved video file name.

        Returns:
            A dictionary containing data for the ComfyUI front-end widget.

        Raises:
            RuntimeError: If video paths are invalid or saving/metadata extraction fails.
        """
        try:
            if not video_paths:
                raise APIInputError("'video_paths' must be provided and not empty.")

            dest_dir = os.path.join("output", "veo")
            os.makedirs(dest_dir, exist_ok=True)

            videos_output_for_ui: List[Dict[str, Any]] = []

            for video_path in video_paths:
                if not (
                    video_path and isinstance(video_path, str) and video_path.strip()
                ):
                    continue  # Skip empty/invalid string paths

                video_path_abs = os.path.abspath(video_path)

                if not os.path.exists(video_path_abs):
                    raise APIInputError(f"Video file not found: {video_path_abs}")

                ext = Path(video_path_abs).suffix.lower()
                if ext not in SUPPORTED_VIDEO_EXTENSIONS:
                    raise APIInputError(
                        f"Unsupported video format: {ext}. Supported formats: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
                    )

                video_file_basename = os.path.basename(video_path_abs)
                video_subfolder = ""
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
                    print(
                        f"Warning: Could not get video metadata for {video_file_basename} using moviepy: {moviepy_e}"
                    )
                    # Fallback for format if moviepy fails.
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
                    dest_name = f"{save_video_file_prefix}_{timestamp}_{file_hash}{ext}"
                    dest_path_relative = os.path.join("veo", dest_name)
                    dest_path_abs = os.path.join("output", dest_path_relative)

                    shutil.copy2(video_path_abs, dest_path_abs)
                    print(f"Video copied to: {dest_path_abs}")

                    video_file_for_ui = dest_name
                    video_subfolder = "veo"
                    file_type = "output"
                else:
                    # If not saving, use the original temp path relative to the COMIFY_TEMP_DIR
                    # This path manipulation ensures the ComfyUI API can find the file in the temp directory.
                    temp_dir_name = os.path.normpath(folder_paths.get_temp_directory())
                    if os.path.normpath(video_path_abs).startswith(temp_dir_name):
                        video_file_for_ui = os.path.normpath(video_path_abs)[
                            len(temp_dir_name) :
                        ].lstrip(os.path.sep)
                    else:
                        video_file_for_ui = os.path.basename(video_path_abs)

                    video_subfolder = ""
                    file_type = "temp"

                video_item_for_ui = {
                    "filename": video_file_for_ui,
                    "subfolder": video_subfolder,
                    "type": file_type,
                    "duration": duration,
                    "width": width,
                    "height": height,
                    "format": video_format,
                }
                videos_output_for_ui.append(video_item_for_ui)

            if not videos_output_for_ui:
                raise APIExecutionError("No valid video outputs were processed.")

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

        except APIInputError as e:
            raise RuntimeError(f"Preview/Save Video Input Error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"Preview/Save Video Execution Error: {e}") from e
        except Exception as e:
            print(f"An unexpected error occurred in VeoVideoSaveAndPreview: {str(e)}")
            return {"ui": {"video": [], "error": str(e)}}


NODE_CLASS_MAPPINGS = {
    "VeoVideoToVHSNode": VeoVideoToVHSNode,
    "VeoVideoSaveAndPreview": VeoVideo,
}
