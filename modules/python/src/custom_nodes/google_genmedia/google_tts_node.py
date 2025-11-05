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
import wave
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

from .constants import GoogleTTSModel
from .custom_exceptions import APIExecutionError, ConfigurationError
from .google_tts_api import GoogleTTSAPI


class GoogleTTSNode:
    """
    ComfyUI node for Google's Text-to-Speech API, supporting Gemini and Chirp models.
    It parses the WAV response from the API and returns an audio tensor.
    """

    def __init__(self) -> None:
        """
        Initializes the GoogleTTSNode.
        """
        pass

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        """
        Defines the input types for the ComfyUI node.

        Returns:
            A dictionary specifying the required and optional input parameters.
        """
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "Hello! I am a generative voice, designed by Google.",
                        "placeholder": "Enter the text to synthesize...",
                    },
                ),
                "model_name": (
                    [model.name for model in GoogleTTSModel],
                    {"default": GoogleTTSModel.GEMINI_PRO_TTS.name},
                ),
                "language_code": (
                    "STRING",
                    {"default": "en-US", "placeholder": "e.g., en-US, es-ES"},
                ),
                "voice_name": (
                    "STRING",
                    {"default": "Charon", "placeholder": "e.g., Charon, chirp-us-1"},
                ),
                "sample_rate": (
                    "INT",
                    {"default": 24000, "min": 8000, "max": 48000, "step": 100},
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
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Describe the primary driver of the overall emotional tone and delivery (Gemini models only)...",
                    },
                ),
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
    CATEGORY = "Google AI"

    def execute_synthesis(
        self,
        gcp_project_id: Optional[str],
        gcp_region: Optional[str],
        language_code: str,
        model_name: str,
        prompt: Optional[str],
        sample_rate: int,
        speed: float,
        text: str,
        voice_name: str,
        volume_gain_db: float,
    ) -> Tuple[Dict[str, Any],]:
        """
        Executes the text-to-speech synthesis process.

        Args:
            gcp_project_id: The GCP project ID.
            gcp_region: The GCP region.
            language_code: The language and region of the voice.
            model_name: The TTS model to use.
            prompt: An optional descriptive prompt for the voice (Gemini only).
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
        if not text or not text.strip():
            raise ConfigurationError("Text input cannot be empty.")

        try:
            api_client = GoogleTTSAPI(project_id=gcp_project_id, region=gcp_region)

            audio_data_binary, _ = api_client.synthesize(
                language_code=language_code,
                model_name=model_name,
                prompt=prompt,
                sample_rate=sample_rate,
                speed=speed,
                text=text,
                voice_name=voice_name,
                volume_gain_db=volume_gain_db,
            )

            if not audio_data_binary:
                raise APIExecutionError("API call returned no audio data.")

            output_audio = self._process_wav_to_tensor(audio_data_binary)
            return (output_audio,)

        except (ConfigurationError, APIExecutionError) as e:
            raise RuntimeError(str(e)) from e
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred: {e}") from e

    def _process_wav_to_tensor(self, audio_data_binary: bytes) -> Dict[str, Any]:
        """
        Parses WAV binary data and converts it to a ComfyUI-compatible audio tensor.

        Args:
            audio_data_binary: The raw WAV audio data in bytes.

        Returns:
            A dictionary containing the audio waveform as a PyTorch tensor and the sample rate.

        Raises:
            RuntimeError: If the WAV data is corrupted or in an unsupported format.
        """
        buffer = io.BytesIO(audio_data_binary)
        try:
            with wave.open(buffer, "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                actual_sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                frames = wf.readframes(n_frames)

                if sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 1:
                    dtype = np.uint8
                else:
                    raise RuntimeError(
                        f"Unsupported sample width from WAV: {sampwidth}"
                    )

                waveform_np = np.frombuffer(frames, dtype=dtype)

                # Normalize to float32
                if dtype == np.int16:
                    waveform_np = waveform_np.astype(np.float32) / 32768.0
                elif dtype == np.uint8:
                    waveform_np = (waveform_np.astype(np.float32) - 128.0) / 128.0

                audio_tensor = torch.from_numpy(waveform_np)
                audio_tensor = (
                    audio_tensor.reshape(-1, n_channels).transpose(0, 1).unsqueeze(0)
                )

                print(f"Final audio tensor created with shape: {audio_tensor.shape}")
                return {"waveform": audio_tensor, "sample_rate": actual_sample_rate}

        except wave.Error as e:
            raise RuntimeError(f"Failed to read WAV data from API response: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to process audio tensor: {e}") from e


NODE_CLASS_MAPPINGS = {"GoogleTTS": GoogleTTSNode}
NODE_DISPLAY_NAME_MAPPINGS = {"GoogleTTS": "Google Text-to-Speech"}
