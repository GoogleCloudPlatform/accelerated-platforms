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

from typing import Optional, Tuple

from google import genai
from google.genai import types

from . import utils
from .base import VertexAIClient
from .constants import (
    AUDIO_MIME_TYPES,
    GEMINI_USER_AGENT,
    IMAGE_MIME_TYPES,
    VIDEO_MIME_TYPES,
    GeminiModel,
    ThresholdOptions,
)
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .logger import get_node_logger
from .retry import api_error_retry

logger = get_node_logger(__name__)


class GeminiNode25(VertexAIClient):
    def __init__(
        self, gcp_project_id: Optional[str] = None, gcp_region: Optional[str] = None
    ):
        """
        Initializes the Gemini client.
        Args:
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.

        Raises:
            ConfigurationError: If client initialization fails.
        """
        super().__init__(
            gcp_project_id=gcp_project_id,
            gcp_region=gcp_region,
            user_agent=GEMINI_USER_AGENT,
        )
        logger.info(
            f"genai.Client initialized for Vertex AI project: {self.project_id}, location: {self.region}"
        )

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

    @api_error_retry
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
        """Generates content using the Gemini API based on the provided prompt and parameters.

        This method constructs a request to the Gemini API, including text and
        optional multimedia content (images, videos, audio). It configures
        generation parameters such as temperature, token limits, and safety
        settings to control the output.

        Args:
            prompt (str): The main text prompt for the model.
            model (str): The name of the Gemini model to use (e.g., "gemini-pro").
            temperature (float): Controls the randomness of the output. Higher values
                                  (e.g., 0.8) make the output more random, while lower
                                  values (e.g., 0.2) make it more focused and deterministic.
                                  Typically ranges from 0.0 to 1.0.
            max_output_tokens (int): The maximum number of tokens to generate in the response.
            top_p (float): The maximum cumulative probability of tokens to consider.
                           Tokens are sorted by probability, and only the most likely
                           tokens whose cumulative probability does not exceed `top_p` are
                           considered. Typically ranges from 0.0 to 1.0.
            top_k (int): The maximum number of tokens to consider when generating the next token.
                         The model selects from the `top_k` most probable tokens.
            candidate_count (int): The number of alternative responses to generate.
                                   The API will return `candidate_count` responses,
                                   from which you can choose the best one.
            stop_sequences (str): A comma-separated string of sequences at which to stop
                                   the generation. The model will stop generating content
                                   once it encounters any of these sequences.
            response_mime_type (str): The desired MIME type of the response, e.g., "text/plain"
                                      or "application/json".
            harassment_threshold (str): Safety threshold for harassment content.
                                        Expected values depend on `ThresholdOptions` enum
                                        (e.g., "BLOCK_NONE", "BLOCK_LOW_AND_ABOVE").
            hate_speech_threshold (str): Safety threshold for hate speech content.
            sexually_explicit_threshold (str): Safety threshold for sexually explicit content.
            dangerous_content_threshold (str): Safety threshold for dangerous content.
            system_instruction (str, optional): An optional system instruction to guide the
                                                model's behavior or style. Defaults to "".
            image_file_path (str, optional): Path to an image file to include in the prompt.
                                             Defaults to "".
            image_mime_type (str, optional): MIME type of the image file. Defaults to "image/png".
            video_file_path (str, optional): Path to a video file to include in the prompt.
                                             Defaults to "".
            video_mime_type (str, optional): MIME type of the video file. Defaults to "video/mp4".
            audio_file_path (str, optional): Path to an audio file to include in the prompt.
                                             Defaults to "".
            audio_mime_type (str, optional): MIME type of the audio file. Defaults to "audio/mp3".
            gcp_project_id (str, optional): GCP project ID to use for Vertex AI. Defaults to "".
            gcp_region (str, optional): GCP region to use for Vertex AI. Defaults to "".

        Returns:
            tuple: A tuple containing the generated text as the first element. If content
                   is blocked, it will contain a message indicating the reason and safety
                   ratings. If an error occurs, it will contain an error message.

        Raises:
            RuntimeError: If API configuration fails, or if content generation encounters an API error.
        """
        # Re-initialize the client to handle optional credential changes in the node
        try:
            init_project_id = gcp_project_id if gcp_project_id else None
            init_region = gcp_region if gcp_region else None
            self.__init__(gcp_project_id=init_project_id, gcp_region=init_region)
        except ConfigurationError as e:
            raise RuntimeError(f"Gemini API Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during client initialization: {e}"
            ) from e

        # Prepare the request payload
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
            safety_settings = []
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=ThresholdOptions[harassment_threshold].value,
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=ThresholdOptions[hate_speech_threshold].value,
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=ThresholdOptions[sexually_explicit_threshold].value,
                )
            )
            safety_settings.append(
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=ThresholdOptions[dangerous_content_threshold].value,
                )
            )

            gen_config_obj.safety_settings = safety_settings
            # Prepare contents (prompt, text, image, video, audio)
            contents = [types.Part.from_text(text=prompt)]
            image_content = (
                utils.prep_for_media_conversion(image_file_path, image_mime_type)
                if image_file_path
                else logger.info(f"No image provided")
            )
            if image_content:
                contents.append(image_content)
            else:
                logger.info(
                    f"Image path '{image_file_path}' provided but content not retrieved or file not found."
                )

            video_content = (
                utils.prep_for_media_conversion(video_file_path, video_mime_type)
                if video_file_path
                else logger.info(f"No video provided")
            )
            if video_content:
                contents.append(video_content)
            else:
                logger.info(
                    f"Video path '{video_file_path}' provided but content not retrieved or file not found."
                )

            audio_content = (
                utils.prep_for_media_conversion(audio_file_path, audio_mime_type)
                if audio_file_path
                else logger.info(f"No audio provided")
            )
            if audio_content:
                contents.append(audio_content)
            else:
                logger.info(
                    f"Audio path '{audio_file_path}' provided but content not retrieved or file not found."
                )
            # Prepare system instruction
            system_instruction_parts = []
            if system_instruction:
                system_instruction_parts.append(
                    types.Part.from_text(text=system_instruction)
                )

            gen_config_obj.system_instruction = (
                system_instruction_parts if system_instruction_parts else None
            )
            # Make the API call
            logger.info(
                f"Making Gemini API call with the following Model : {GeminiModel[model]} , config {gen_config_obj}"
            )  # Prepare Safety Settings

        except (KeyError, FileNotFoundError) as e:
            raise RuntimeError(f"Invalid input provided: {e}") from e
        except APIInputError as e:
            raise RuntimeError(f"Gemini API Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during request preparation: {e}"
            ) from e

        # Make the API call
        logger.info(
            f"Making Gemini API call with the following Model : {GeminiModel[model]} , config {gen_config_obj}"
        )
        response = self.client.models.generate_content(
            config=gen_config_obj,
            contents=contents,
            model=GeminiModel[model],
        )

        # Process the response
        try:
            # Extract and return the generated text
            generated_text = ""
            if response.candidates:
                generated_text = response.candidates[0].content.parts[0].text

            else:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    generated_text = f"Content blocked by safety filter: {response.prompt_feedback.block_reason}"
                    if response.prompt_feedback.safety_ratings:
                        for rating in response.prompt_feedback.safety_ratings:
                            generated_text += f"\n  - Category: {rating.category.name}, Probability: {rating.probability.name}"
                else:
                    generated_text = "No content generated."

            return (generated_text,)
        except (AttributeError, IndexError) as e:
            raise RuntimeError(
                f"Failed to parse API response, unexpected structure: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during response processing: {e}"
            ) from e


NODE_CLASS_MAPPINGS = {"GeminiNode25": GeminiNode25}

NODE_DISPLAY_NAME_MAPPINGS = {"GeminiNode25": "Gemini 2.5"}
