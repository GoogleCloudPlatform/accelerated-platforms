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

# This is a preview version of gemini custom node

from typing import Optional

from google import genai
from google.genai import types

from . import exceptions, utils
from .config import GoogleGenAIBaseAPI
from .config import get_gcp_metadata
from .constants import (
    AUDIO_MIME_TYPES,
    GEMINI_USER_AGENT,
    IMAGE_MIME_TYPES,
    VIDEO_MIME_TYPES,
    GeminiModel,
    ThresholdOptions,
)
from .retry import retry_on_api_error


class GeminiNode25(GoogleGenAIBaseAPI):
    def __init__(
        self,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ):
        """
        Initializes the Gemini client.

        Args:
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.
        """
        super().__init__(gcp_project_id, gcp_region, GEMINI_USER_AGENT)

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

    @retry_on_api_error()
    def _generate_content(self, model, contents, config):
        print(
            f"Making Gemini API call with the following Model : {model} , config {config}"
        )
        return self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

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
    ):
        """Generates content using the Gemini API based on the provided prompt and parameters.

        This method constructs a request to the Gemini API, including text and
        optional multimedia content (images, videos, audio). It configures
        generation parameters such as temperature, token limits, and safety
        settings to control the output.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        # Stage 1: Client Initialization
        try:
            init_project_id = gcp_project_id if gcp_project_id else None
            init_region = gcp_region if gcp_region else None
            self.__init__(gcp_project_id=init_project_id, gcp_region=init_region)
        except exceptions.APIInitializationError as e:
            print(f"Failed to initialize Gemini client: {e}")
            raise RuntimeError(f"Failed to initialize Gemini client: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during client initialization: {e}")
            raise RuntimeError(f"An unexpected error occurred during client initialization: {e}")

        # Stage 2: Prepare Request Payload
        try:
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
            safety_settings = [
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
            gen_config_obj.safety_settings = safety_settings

            # Prepare contents (prompt, text, image, video, audio)
            contents = [types.Part.from_text(text=prompt)]
            if image_file_path:
                image_content = utils.prep_for_media_conversion(
                    image_file_path, image_mime_type
                )
                if image_content:
                    contents.append(image_content)
            if video_file_path:
                video_content = utils.prep_for_media_conversion(
                    video_file_path, video_mime_type
                )
                if video_content:
                    contents.append(video_content)
            if audio_file_path:
                audio_content = utils.prep_for_media_conversion(
                    audio_file_path, audio_mime_type
                )
                if audio_content:
                    contents.append(audio_content)

            # Prepare system instruction
            if system_instruction:
                gen_config_obj.system_instruction = [
                    types.Part.from_text(text=system_instruction)
                ]

        except Exception as e:
            print(f"Failed to prepare API request payload: {e}")
            raise RuntimeError(f"Failed to prepare API request payload: {e}")

        # Stage 3: Make API call
        try:
            response = self._generate_content(
                model=GeminiModel[model].value,
                contents=contents,
                config=gen_config_obj,
            )
        except Exception as e:
            print(f"Gemini API call failed: {e}")
            raise RuntimeError(f"Gemini API call failed: {e}")

        # Stage 4: Process response
        try:
            generated_text = ""
            if not response.candidates:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    generated_text = f"Content blocked due to safety filters on the prompt. Reason: {response.prompt_feedback.block_reason}"
                    if response.prompt_feedback.safety_ratings:
                        for rating in response.prompt_feedback.safety_ratings:
                            generated_text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
                else:
                    generated_text = "No content generated. The response was empty."
            else:  # We have candidates
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    generated_text = candidate.content.parts[0].text
                elif (
                    hasattr(candidate, "finish_reason")
                    and candidate.finish_reason.name == "SAFETY"
                ):
                    generated_text = f"Content generation stopped due to safety filters. Finish reason: {candidate.finish_reason.name}"
                    if candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            generated_text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
                elif hasattr(candidate, "finish_reason"):
                    generated_text = f"No content generated. Finish reason: {candidate.finish_reason.name}"
                else:
                    generated_text = "No content generated. Candidate was empty."

            return (generated_text,)
        except Exception as e:
            print(f"Failed to process API response: {e}")
            raise RuntimeError(f"Failed to process API response: {e}")


NODE_CLASS_MAPPINGS = {"GeminiNode25": GeminiNode25}

NODE_DISPLAY_NAME_MAPPINGS = {"GeminiNode25": "Gemini 2.5"}
