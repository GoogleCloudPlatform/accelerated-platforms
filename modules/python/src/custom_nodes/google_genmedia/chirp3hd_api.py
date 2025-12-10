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

import logging
import re
from typing import Optional

from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import texttospeech

from . import utils
from .base import VertexAIClient
from .constants import CHIRP3_USER_AGENT
from .custom_exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def classify_string(text: str) -> dict:
    """
    Classifies a string as 'ssml', 'markup', or 'text'.

    Args:
        text: The string to classify.

    Returns:
        The dictionary with classification.
    """
    if re.search(r"<.*?>", text):
        return {"ssml": text}
    elif re.search(r"\[.*?\]", text):
        return {"markup": text}
    else:
        return {"text": text}


class Chirp3API(VertexAIClient):
    """
    Handles all communication with the Google Cloud Text-to-Speech API for Chirp3 models.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        user_agent: Optional[str] = CHIRP3_USER_AGENT,
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
            print(f"Initialized Google TTS Client. with User-Agent: {user_agent}")
        except Exception as e:
            raise ConfigurationError(
                "Failed to initialize Google TTS Client. "
                "Please ensure you are authenticated (e.g., `gcloud auth application-default login`). "
                f"Error: {e}"
            )

    def synthesize(
        self,
        language_code: str,
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
            language_code: The language code for the voice.
            voice_name: The name of the voice to use.
            sample_rate: The desired sample rate of the audio.
            speed: The speaking rate of the synthesized speech.
            volume_gain_db: The volume gain in dB.

        Returns:
            A tuple containing the raw audio content (bytes) and the sample rate (int).


        Raises:
            APIInputError: If input parameters are invalid.
            APIExecutionError: If music generation fails due to API or unexpected issues.
        """

        synthesis_input_params = classify_string(text)
        voice_params = {"language_code": language_code, "name": voice_name}

        logger.info(f"  - Synthesis Input: {synthesis_input_params}")
        logger.info(f"  - Voice Params: {voice_params}")

        return utils.generate_speech_from_text(
            client=self.client,
            sample_rate=sample_rate,
            speed=speed,
            synthesis_input_params=synthesis_input_params,
            voice_params=voice_params,
            volume_gain_db=volume_gain_db,
        )
