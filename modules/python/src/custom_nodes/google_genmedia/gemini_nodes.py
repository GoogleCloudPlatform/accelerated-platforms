# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This is a preview version of gemini custom node
import logging
from typing import List, Optional, Any, Tuple

from google.auth import exceptions as auth_exceptions
from google.api_core import exceptions as api_core_exceptions
from google.genai import errors as genai_errors
from google.genai import types

from . import utils
from .constants import (
    AUDIO_MIME_TYPES,
    GEMINI_USER_AGENT,
    IMAGE_MIME_TYPES,
    VIDEO_MIME_TYPES,
    GeminiModel,
    ThresholdOptions,
)


class GeminiNode25:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        # ... [INPUT_TYPES code remains exactly the same as your version] ...
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
                "max_output_tokens": ("INT", {"default": 8192, "min": 1, "max": 8192}),
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
                    {
                        "optional": True,
                        "placeholder": "/path/to/your/image.png",
                        "tooltip": "the absolute path of the image e.g output/file.png",
                    },
                ),
                "image_mime_type": (
                    [image_type for image_type in IMAGE_MIME_TYPES],
                    {"optional": True, "default": "image/png"},
                ),
                "video_file_path": (
                    "STRING",
                    {
                        "optional": True,
                        "placeholder": "/path/to/your/video.mp4",
                        "tooltip": "the absolute path of the video e.g output/file.mp4",
                    },
                ),
                "video_mime_type": (
                    [video_type for video_type in VIDEO_MIME_TYPES],
                    {"optional": True, "default": "video/mp4"},
                ),
                "audio_file_path": (
                    "STRING",
                    {
                        "optional": True,
                        "placeholder": "/path/to/your/audio.mp3",
                        "tooltip": "the absolute path of the audio e.g output/file.mp3",
                    },
                ),
                "audio_mime_type": (
                    [audio_type for audio_type in AUDIO_MIME_TYPES],
                    {"optional": True, "default": "audio/mp3"},
                ),
                "gcp_project_id": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "GCP project id where Vertex AI API will query Gemini",
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

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("generated_output",)
    FUNCTION = "generate_content"
    CATEGORY = "Google AI/Gemini"

    def _build_generation_config(
        self,
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
        system_instruction: str,
    ) -> types.GenerateContentConfig:
        """Helper to build the generation and safety config."""

        # Prepare GenerationConfig
        gen_config_obj = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k,
            candidate_count=candidate_count,
        )
        if stop_sequences:
            gen_config_obj.stop_sequences = [
                s.strip() for s in stop_sequences.split(",") if s.strip()
            ]

        if response_mime_type != "text/plain":
            gen_config_obj.response_mime_type = response_mime_type

        # Prepare Safety Settings
        gen_config_obj.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=ThresholdOptions[harassment_threshold].value,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=ThresholdOptions[hate_speech_threshold].value,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=ThresholdOptions[sexually_explicit_threshold].value,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=ThresholdOptions[dangerous_content_threshold].value,
            ),
        ]

        # Prepare system instruction
        if system_instruction:
            gen_config_obj.system_instruction = [
                types.Part.from_text(text=system_instruction)
            ]

        return gen_config_obj

    def _prepare_contents(
        self,
        prompt: str,
        image_file_path: str,
        image_mime_type: str,
        video_file_path: str,
        video_mime_type: str,
        audio_file_path: str,
        audio_mime_type: str,
    ) -> List[types.Part]:
        """Helper to build the multimodal contents list."""
        contents = [types.Part.from_text(text=prompt)]

        media_paths = [
            (image_file_path, image_mime_type, "Image"),
            (video_file_path, video_mime_type, "Video"),
            (audio_file_path, audio_mime_type, "Audio"),
        ]

        for path, mime, media_type in media_paths:
            if path and path.strip():
                media_content = utils.prep_for_media_conversion(path, mime)
                if media_content:
                    contents.append(media_content)
                else:
                    logging.warning(
                        f"{media_type} path '{path}' provided but content not retrieved or file not found."
                    )
            else:
                logging.info(f"No {media_type} provided.")

        return contents

    def _parse_response(self, response: Any) -> str:
        """Helper to safely parse the API response."""
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                return candidate.content.parts[0].text
            elif (
                hasattr(candidate, "finish_reason")
                and candidate.finish_reason.name == "SAFETY"
            ):
                text = f"Content generation stopped due to safety filters. Finish reason: {candidate.finish_reason.name}"
                if candidate.safety_ratings:
                    for rating in candidate.safety_ratings:
                        text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
                return text
            elif hasattr(candidate, "finish_reason"):
                return f"No content generated. Finish reason: {candidate.finish_reason.name}"

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            text = f"Prompt blocked due to safety filters. Reason: {response.prompt_feedback.block_reason}"
            if response.prompt_feedback.safety_ratings:
                for rating in response.prompt_feedback.safety_ratings:
                    text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
            return text

        return "No content generated. The response was empty."

    def generate_content(
        self,
        prompt: str,
        model: str,
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
        gcp_project_id: str = "",
        gcp_region: str = "",
    ) -> Tuple[str,]:

        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) == 0:
            raise ValueError("Prompt cannot be empty for content generation.")

        try:
            # 1. Initialize Client (catches auth/permission errors on init)
            client = utils.get_genai_client(
                gcp_project_id, gcp_region, GEMINI_USER_AGENT
            )

            # 2. Build Config (catches config value errors)
            gen_config_obj = self._build_generation_config(
                temperature,
                max_output_tokens,
                top_p,
                top_k,
                candidate_count,
                stop_sequences,
                response_mime_type,
                harassment_threshold,
                hate_speech_threshold,
                sexually_explicit_threshold,
                dangerous_content_threshold,
                system_instruction,
            )

            # 3. Prepare Content (catches file errors)
            contents = self._prepare_contents(
                prompt,
                image_file_path,
                image_mime_type,
                video_file_path,
                video_mime_type,
                audio_file_path,
                audio_mime_type,
            )

            # 4. Make the API call
            logging.info(
                f"Making Gemini API call with Model: {GeminiModel[model].value}"
            )
            response = client.models.generate_content(
                model=GeminiModel[model].value,
                contents=contents,
                config=gen_config_obj,
            )

            # 5. Safely parse and return the response
            generated_text = self._parse_response(response)
            return (generated_text,)

        # --- Expanded and correct exception catching ---
        except auth_exceptions.DefaultCredentialsError as e:
            error_msg = (
                "Authentication failed. Please configure your GCP credentials. "
                "See https://cloud.google.com/docs/authentication/provide-credentials-adc"
            )
            logging.error(f"{error_msg}: {e}")
            return (f"Error: {error_msg}",)

        except api_core_exceptions.PermissionDenied as e:
            error_msg = (
                "Permission denied. Check your GCP project/region and API permissions."
            )
            logging.error(f"{error_msg}: {e}")
            return (f"Error: {error_msg}",)

        except (
            genai_errors.GoogleAPICallError,
            api_core_exceptions.GoogleAPICallError,
        ) as e:
            error_msg = f"Google API call failed: {e}"
            logging.error(error_msg)
            return (f"Error: {error_msg}",)

        except ValueError as e:
            # Catches ValueErrors from client init, config, or prompt check
            error_msg = f"Configuration error: {e}"
            logging.error(error_msg)
            return (f"Error: {error_msg}",)

        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred: {e}"
            logging.error(error_msg, exc_info=True)
            return (f"Error: {error_msg}",)


NODE_CLASS_MAPPINGS = {"GeminiNode25": GeminiNode25}
NODE_DISPLAY_NAME_MAPPINGS = {"GeminiNode25": "Gemini 2.5"}
