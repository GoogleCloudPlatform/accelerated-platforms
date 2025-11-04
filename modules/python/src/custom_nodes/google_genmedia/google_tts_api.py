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

import re
from typing import Optional

from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import texttospeech

from .base import GoogleCloudClientBase
from .constants import GOOGLE_GOOGLE_TTS_USER_AGENT, GoogleTTSModel
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .retry import api_error_retry


def classify_string(text: str) -> str:
    """
    Classifies a string as 'ssml', 'markup', or 'text'.

    Args:
        text: The string to classify.

    Returns:
        The classification of the string.
    """
    if re.search(r"<.*?>", text):
        return "ssml"
    elif re.search(r"\[.*?\]", text):
        return "markup"
    else:
        return "text"


class GoogleTTSAPI(GoogleCloudClientBase):
    """
    Handles all communication with the Google Cloud Text-to-Speech API.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        user_agent: Optional[str] = GOOGLE_GOOGLE_TTS_USER_AGENT,
    ):
        """
        Initializes the TextToSpeechClient.

        Args:
            project_id: The GCP project ID. Overrides metadata lookup.
            region: The GCP region. Overrides metadata lookup.
            user_agent: The user agent to use for the client.

        Raises:
            ConfigurationError: If client initialization fails.
        """
        super().__init__(gcp_project_id=project_id, gcp_region=region)

        try:
            client_info = ClientInfo(user_agent=user_agent) if user_agent else None
            self.client = texttospeech.TextToSpeechClient(client_info=client_info)
            print(
                f"[GoogleTTSAPI] Initialized TextToSpeechClient with User-Agent: {user_agent}"
            )
        except Exception as e:
            raise ConfigurationError(
                "Failed to initialize Google TTS Client. "
                "Please ensure you are authenticated (e.g., `gcloud auth application-default login`). "
                f"Error: {e}"
            )

    @api_error_retry
    def synthesize(
        self,
        language_code: str,
        model_name: str,
        prompt: Optional[str],
        sample_rate: int,
        speed: float,
        text: str,
        voice_name: str,
        volume_gain_db: float,
    ) -> tuple[bytes, int]:
        """
        Synthesizes speech and returns the raw audio binary content and sample rate.

        Args:
            text: The text to synthesize.
            model_name: The name of the TTS model to use.
            language_code: The language code for the voice.
            voice_name: The name of the voice to use.
            sample_rate: The desired sample rate of the audio.
            speed: The speaking rate of the synthesized speech.
            volume_gain_db: The volume gain in dB.
            prompt: Optional prompt for guiding synthesis (Gemini models only).

        Returns:
            A tuple containing the raw audio content (bytes) and the sample rate (int).


        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If music generation fails due to API or unexpected issues.
        """
        print(
            f"[GoogleTTSAPI] Synthesizing speech with model: {model_name}, voice: {voice_name} @ {sample_rate}Hz"
        )
        model_name_value = GoogleTTSModel[model_name].value
        print(f"  - Picked model: {model_name_value}")

        text_type = classify_string(text)
        print(f"  - Classified input as: {text_type}")

        if model_name_value == GoogleTTSModel.CHIRP3_HD_TTS.value:
            # Chirp model
            if text_type == "ssml":
                synthesis_input_params = {"ssml": text}
            elif text_type == "markup":
                synthesis_input_params = {"markup": text}
            else:
                synthesis_input_params = {"text": text}
            final_voice_name = f"{language_code}-{model_name_value}-{voice_name}"
            voice_params = {"language_code": language_code, "name": final_voice_name}
        else:
            # Gemini Models
            synthesis_input_params = {"text": text}
            final_voice_name = voice_name
            voice_params = {
                "language_code": language_code,
                "name": final_voice_name,
                "model_name": model_name_value,
            }
            # Prompt is only supported for Gemini models
            if prompt:
                synthesis_input_params["prompt"] = prompt

        print(f"  - Synthesis Input: {synthesis_input_params}")
        print(f"  - Voice Params: {voice_params}")

        synthesis_input = texttospeech.SynthesisInput(**synthesis_input_params)
        voice = texttospeech.VoiceSelectionParams(**voice_params)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            speaking_rate=speed,
            volume_gain_db=volume_gain_db,
        )
        print(f"  - Audio Config: {audio_config}")

        response = self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        print(
            f"  - Received audio content of length: {len(response.audio_content)} bytes"
        )
        return response.audio_content, sample_rate
