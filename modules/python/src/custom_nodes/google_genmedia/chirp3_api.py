# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
API wrapper for Google Cloud Text-to-Speech with Chirp 3 HD voices.
"""
import base64
from collections import namedtuple
from typing import Optional
from google.api_core.client_options import ClientOptions
from google.cloud import texttospeech
from google.api_core.gapic_v1.client_info import ClientInfo

# Import the custom exceptions
from .base import VertexAIClient
from .custom_exceptions import APIExecutionError, ConfigurationError

# Define a user agent for requests
CHIRP3_USER_AGENT = "comfyui-google-genmedia-node"


class Chirp3API(VertexAIClient):
    """
    A class to interact with the Google Cloud Text-to-Speech API for Chirp 3 voices.
    """

    def __init__(
        self, project_id: Optional[str] = None, region: Optional[str] = "global"
    ):
        """
        Initializes the TextToSpeechClient.

        Args:
            project_id: The GCP project ID. If None, tries to find it in env vars.
            region: The GCP region for the TTS API endpoint. Defaults to "global".
        """
        super().__init__(
            gcp_project_id=project_id, gcp_region=region, user_agent=CHIRP3_USER_AGENT
        )

        try:
            api_endpoint = (
                f"{self.region}-texttospeech.googleapis.com"
                if self.region != "global"
                else "texttospeech.googleapis.com"
            )
            client_options = ClientOptions(api_endpoint=api_endpoint)
            self.client = texttospeech.TextToSpeechClient(
                client_options=client_options,
                client_info=ClientInfo(user_agent=CHIRP3_USER_AGENT),
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize TextToSpeechClient: {e}")

    def generate_audio(
        self,
        text: str,
        voice_name: str,
        language_code: str,
        sample_rate_hertz: int = 24000,
    ) -> dict:
        """
        Generates raw audio data from text using a Chirp 3 HD voice.

        Args:
            text: The text to synthesize.
            voice_name: The name of the voice (e.g., "Aoede").
            language_code: The language code (e.g., "en-US").
            sample_rate_hertz: The sample rate of the audio. Chirp's native rate is 24000.

        Returns:
            A dictionary containing the raw audio content and sample rate.

        Raises:
            APIExecutionError: If the API call fails.
        """
        if not self.client:
            raise ConfigurationError("Text-to-Speech client is not initialized.")

        try:
            input_text = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate_hertz,
            )

            response = self.client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config,
            )

            return {"audio_content": response.audio_content, "sample_rate": sample_rate_hertz}
        except Exception as e:
            raise APIExecutionError(f"Failed to generate audio: {e}")

