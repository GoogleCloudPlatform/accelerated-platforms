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
from typing import Any, Dict, Optional, Tuple

from .chirp3hd_api import Chirp3API
from .constants import CHIRP3_HD_MODEL
from .custom_exceptions import APIExecutionError, ConfigurationError
from .utils import get_tts_voices_and_languages, load_audio_from_bytes


class Chirp3Node:
    """
    A ComfyUI node for Google's Text-to-Speech API, specifically for the Chirp3 HD model.
    It synthesizes text into speech and returns an audio tensor.
    """

    def __init__(self) -> None:
        """
        Initializes the Chirp3Node.
        """
        pass

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        """
        Defines the input types and widgets for the ComfyUI node.

        Returns:
            A dictionary specifying the required and optional input parameters.
        """
        dynamic_voices, dynamic_langs, voice_map = get_tts_voices_and_languages(
            model_to_include=CHIRP3_HD_MODEL
        )
        cls.voice_id_map = voice_map
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "label_on": True,
                        "multiline": True,
                        "default": "Hello! I am a generative voice, designed by Google.",
                        "placeholder": "Enter the text to synthesize...",
                    },
                ),
                "language_code": (
                    dynamic_langs,
                    {
                        "default": (
                            dynamic_langs[0] if len(dynamic_langs) > 16 else "en-US"
                        )
                    },
                ),
                "voice_name": (
                    dynamic_voices,
                    {"default": (dynamic_voices[0] if dynamic_voices else "Charon")},
                ),
                "sample_rate": (
                    "INT",
                    {"default": 24000, "min": 8000, "max": 48000, "step": 10},
                ),
                "speed": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.25, "max": 4.0, "step": 0.05},
                ),
                "volume_gain_db": (
                    "FLOAT",
                    {"default": 0.0, "min": -96.0, "max": 16.0, "step": 0.1},
                ),
            },
            "optional": {
                "gcp_project_id": (
                    "STRING",
                    {"default": "", "placeholder": "your-gcp-project-id"},
                ),
                "gcp_region": (
                    "STRING",
                    {"default": "", "placeholder": "us-central1"},
                ),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "execute_synthesis"
    CATEGORY = "Google AI/Chirp3"

    def execute_synthesis(
        self,
        gcp_project_id: Optional[str],
        gcp_region: Optional[str],
        language_code: str,
        sample_rate: int,
        speed: float,
        text: str,
        voice_name: str,
        volume_gain_db: float,
    ) -> Tuple[Dict[str, Any],]:
        """
        Executes the text-to-speech synthesis process using the Chirp3 HD model.

        Args:
            gcp_project_id: The GCP project ID.
            gcp_region: The GCP region.
            language_code: The language and region of the voice.
            sample_rate: The desired sample rate for the audio.
            speed: The speaking rate of the audio.
            text: The text to be synthesized into speech.
            voice_name: The name of the voice to use.
            volume_gain_db: The volume gain in dB.

        Returns:
            A tuple containing a dictionary with the audio waveform and sample rate.

        Raises:
            ConfigurationError: If the input text is empty.
            RuntimeError: For errors during API communication or audio processing.
        """
        short_voice_name = self.voice_id_map.get(voice_name)
        if not short_voice_name:
            raise ConfigurationError(
                f"Voice ID lookup failed for selected voice: {voice_name}. "
                "The voice list may be corrupt or outdated."
            )
        if not text or not text.strip():
            raise ConfigurationError("Text input cannot be empty.")

        # Reconstruct the full voice name as per user's specified logic
        full_voice_name = f"{language_code}-{CHIRP3_HD_MODEL}-{short_voice_name}"

        try:
            api_client = Chirp3API(project_id=gcp_project_id, region=gcp_region)

            audio_data_binary, _ = api_client.synthesize(
                language_code=language_code,
                sample_rate=sample_rate,
                speed=speed,
                text=text,
                voice_name=full_voice_name,
                volume_gain_db=volume_gain_db,
            )

            if audio_data_binary is None or len(audio_data_binary) == 0:
                raise APIExecutionError("API call returned no audio data.")

            waveform, r_sample_rate = load_audio_from_bytes(audio_data_binary)
            output_audio = {
                "waveform": waveform.unsqueeze(0),
                "sample_rate": r_sample_rate,
            }
            return (output_audio,)

        except (ConfigurationError, APIExecutionError) as e:
            raise RuntimeError(str(e)) from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred: {e}") from e


NODE_CLASS_MAPPINGS = {"Chirp3Node": Chirp3Node}
NODE_DISPLAY_NAME_MAPPINGS = {"Chirp3Node": "Chirp3 HD"}
