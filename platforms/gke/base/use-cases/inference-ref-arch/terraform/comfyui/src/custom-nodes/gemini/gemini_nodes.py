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

# This is a preview version of gemini custom node
import os
from typing import Optional

import cv2
import numpy as np
from google import genai
from google.genai import types
from PIL import Image

from .config import get_gcp_metadata
from .constants import (
    AUDIO_MIME_TYPES,
    IMAGE_MIME_TYPES,
    THRESHOLD_OPTIONS,
    USER_AGENT,
    VIDEO_MIME_TYPES,
    GeminiModel,
    ThresholdOptions,
)


# Helper Functions for Media Conversion
def media_file_to_genai_part(file_path: str, mime_type: str) -> types.Part:
    """
    Reads a media file (image, audio, or video) and converts it to a genai.types.Part.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            media_bytes = f.read()
        return types.Part.from_data(data=media_bytes, mime_type=mime_type)
    except Exception as e:
        raise IOError(
            f"Could not read media file {file_path} with MIME type {mime_type}: {e}"
        )


class GeminiNode25:
    def __init__(self, project_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initializes the Gemini client.

        Args:
            project_id: The GCP project ID. If None, it will be retrieved from GCP metadata.
            region: The GCP region. If None, it will be retrieved from GCP metadata.

        Raises:
            ValueError: If GCP Project or region cannot be determined.
        """
        self.project_id = project_id or get_gcp_metadata("project/project-id")
        self.region = region or "-".join(
            get_gcp_metadata("instance/zone").split("/")[-1].split("-")[:-1]
        )
        if not self.project_id:
            raise ValueError("GCP Project is required")
        if not self.region:
            raise ValueError("GCP region is required")
        print(f"Project is {self.project_id}, region is {self.region}")
        http_options = genai.types.HttpOptions(headers={"user-agent": USER_AGENT})
        try:
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
                http_options=http_options,
            )
            print(
                f"genai.Client initialized for Vertex AI project: {self.project_id}, location: {self.location}"
            )
        except:
            raise RuntimeError(f"Failed to initialize genai.Client for Vertex AI")

    @classmethod
    def INPUT_TYPES(s):

        return {
            "required": {
                "prompt": (
                    "STRING",
                    {"multiline": True, "default": "Describe the content in detail."},
                ),
                "model": (
                    [model.name for model in GeminiModel],
                    {"default": GeminiModel.GEMINI_PRO.name},
                ),
                # GenerationConfig Parameters
                "temperature": (
                    "FLOAT",
                    {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "max_output_tokens": ("INT", {"default": 2048, "min": 1, "max": 8192}),
                "top_p": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "top_k": ("INT", {"default": 32, "min": 1, "max": 64}),
                "candidate_count": ("INT", {"default": 1, "min": 1, "max": 8}),
                "stop_sequences": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "",
                        "placeholder": "Comma-separated phrases to stop generation",
                    },
                ),
                "response_mime_type": (
                    "STRING",
                    {
                        "default": "text/plain",
                        "combo": ["text/plain", "application/json"],
                    },
                ),
                # Safety Settings
                "harassment_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "hate_speech_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "sexually_explicit_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
                "dangerous_content_threshold": (
                    [threshold_option.name for threshold_option in ThresholdOptions],
                    {"default": ThresholdOptions.BLOCK_MEDIUM_AND_ABOVE.name},
                ),
            },
            "optional": {
                "system_instruction": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Optional system instruction for the model",
                    },
                ),
                "image_file_path": (
                    "STRING",
                    {"optional": True, "placeholder": "/path/to/your/image.png"},
                ),
                "image_mime_type": (
                    [image_type for image_type in IMAGE_MIME_TYPES],
                    {"optional": True, "default": "image/png"},
                ),
                "video_file_path": (
                    "STRING",
                    {"optional": True, "placeholder": "/path/to/your/video.mp4"},
                ),
                "video_mime_type": (
                    [video_type for video_type in VIDEO_MIME_TYPES],
                    {"optional": True, "default": "video/mp4"},
                ),
                "audio_file_path": (
                    "STRING",
                    {"optional": True, "placeholder": "/path/to/your/audio.mp3"},
                ),
                "audio_mime_type": (
                    [audio_type for audio_type in AUDIO_MIME_TYPES],
                    {"optional": True, "default": "audio/mp3"},
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("generated_output",)
    FUNCTION = "generate_content"
    CATEGORY = "Google AI/Gemini"

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        temperature: float,
        max_output_tokens: int,
        top_p: float,
        top_k: int,
        candidate_count: int,
        stop_sequences: str,
        response_mime_type: str,
        harassment_threshold: str,
        hate_speech_threshold: str,
        sexually_explicit_threshold: str,
        dangerous_content_threshold: str,
        system_instruction: str = "",
        image_file_path: str = "",
        image_mime_type: str = "image/png",
        video_file_path: str = "",
        video_mime_type: str = "video/mp4",
        audio_file_path: str = "",
        audio_mime_type: str = "audio/mp3",
    ):

        try:
            # Prepare GenerationConfig
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "top_p": top_p,
                "top_k": top_k,
                "candidate_count": candidate_count,
            }
            if stop_sequences:
                generation_config["stop_sequences"] = [
                    s.strip() for s in stop_sequences.split(",") if s.strip()
                ]

            if response_mime_type != "text/plain":
                generation_config["response_mime_type"] = response_mime_type

            # Prepare Safety Settings
            safety_settings = []

            # threshold_map = {
            #     "BLOCK_NONE": types.HarmBlockThreshold.BLOCK_NONE,
            #     "BLOCK_ONLY_HIGH": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            #     "BLOCK_MEDIUM_AND_ABOVE": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            #     "BLOCK_LOW_AND_ABOVE": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            # }
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=ThresholdOptions[harassment_threshold],
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=ThresholdOptions[hate_speech_threshold],
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=ThresholdOptions[sexually_explicit_threshold],
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=ThresholdOptions[dangerous_content_threshold],
                )
            )

            # Prepare contents (text, image, video, audio)
            contents = [types.Part.from_text(prompt)]

            if image_file_path and os.path.exists(image_file_path):
                try:
                    image_part = media_file_to_genai_part(
                        image_file_path, image_mime_type
                    )
                    contents.append(image_part)
                except Exception as e:
                    print(f"Warning: Could not add image file {image_file_path}: {e}")
            elif image_file_path and not os.path.exists(image_file_path):
                print(
                    f"Warning: Image file path specified but file not found: {image_file_path}"
                )

            if video_file_path and os.path.exists(video_file_path):
                try:
                    video_part = media_file_to_genai_part(
                        video_file_path, video_mime_type
                    )
                    contents.append(video_part)
                except Exception as e:
                    print(f"Warning: Could not add video file {video_file_path}: {e}")
            elif video_file_path and not os.path.exists(video_file_path):
                print(
                    f"Warning: Video file path specified but file not found: {video_file_path}"
                )

            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    audio_part = media_file_to_genai_part(
                        audio_file_path, audio_mime_type
                    )
                    contents.append(audio_part)
                except Exception as e:
                    print(f"Warning: Could not add audio file {audio_file_path}: {e}")
            elif audio_file_path and not os.path.exists(audio_file_path):
                print(
                    f"Warning: Audio file path specified but file not found: {audio_file_path}"
                )

            # Prepare system instruction
            system_instruction_parts = []
            if system_instruction:
                system_instruction_parts.append(
                    types.Part.from_text(system_instruction)
                )

            # Make the API call
            response = self.client.models.generate_content(
                model=GeminiModel[model],
                contents=contents,
                generation_config=generation_config,
                safety_settings=safety_settings,
                system_instruction=(
                    system_instruction_parts if system_instruction_parts else None
                ),
            )

            # Extract and return the generated text
            generated_text = ""
            if response.candidates:
                generated_text = response.candidates[0].text
            else:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    generated_text = f"Content blocked by safety filter: {response.prompt_feedback.block_reason}"
                    if response.prompt_feedback.safety_ratings:
                        for rating in response.prompt_feedback.safety_ratings:
                            generated_text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
                else:
                    generated_text = "No content generated."

            return (generated_text,)

        except Exception as e:
            print(f"An error occurred in calling Gemini API: {e}")
            return (f"Error: {e}",)


NODE_CLASS_MAPPINGS = {"GeminiNode25": GeminiNode25}

NODE_DISPLAY_NAME_MAPPINGS = {"GeminiNode25": "Gemini 2.5"}
