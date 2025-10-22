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

from .constants import CHIRP3_MAX_SAMPLES, MAX_SEED
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .chirp3_api import Chirp3API


class Chirp3TextToAudioNode:
    """A ComfyUI node for generating audio from text prompts using the Google Chirp 3 API."""

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "An energetic electronic dance track.",
                        "placeholder": "Describe the audio you want to generate...",
                    },
                ),
                "sample_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": MAX_SEED,
                        "step": 1,
                        "display": "number",
                    },
                ),
            },
            "optional": {
                "negative_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Elements to avoid (e.g., drums, vocals)...",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "tooltip": "Seed for reproducibility. Set to 0 to let the API handle randomness, which is required for sample_count > 1.",
                    },
                ),
                "gcp_project_id": (
                    "STRING",
                    {"default": "", "placeholder": "your-gcp-project-id"},
                ),
                "gcp_region": ("STRING", {"default": "", "placeholder": "us-central1"}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "generate_audio"
    CATEGORY = "Google AI/Chirp3"

    def generate_audio(
        self,
        prompt: str,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        sample_count: int = 1,
        seed: Optional[int] = None,
    ) -> Tuple[dict,]:
        """
        Generates audio from a text prompt using the Chirp 3 API.

        Args:
            prompt: The text prompt for audio generation.
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            sample_count: The number of audio samples to generate.
            seed: An optional seed for reproducible audio generation.


        Returns:
            A tuple containing a dictionary with the audio waveform and sample rate.

        Raises:
            ConfigurationError: If input parameters are invalid or GCP configuration is missing.
            RuntimeError: If audio generation fails due to API errors or unexpected issues.
        """

        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ConfigurationError("Prompt cannot be empty.")

        if seed != 0 and sample_count > 1:
            raise ConfigurationError(
                "Cannot use a specific 'seed' and 'sample_count' > 1 in the same request."
            )

        if not (1 <= sample_count <= CHIRP3_MAX_SAMPLES):
            raise ConfigurationError(
                f"sample_count must be between 1 and {CHIRP3_MAX_SAMPLES}."
            )

        try:
            chirp3_api = Chirp3API(project_id=gcp_project_id, region=gcp_region)
            audio_data = chirp3_api.generate_audio_from_text(
                negative_prompt=negative_prompt,
                prompt=prompt,
                sample_count=sample_count,
                seed=seed,
            )
        except APIInputError as e:
            raise RuntimeError(f"Input Error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"API Error: {e}") from e
        except ConfigurationError as e:
            raise RuntimeError(f"Configuration Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during audio generation: {e}"
            ) from e
        if not audio_data:
            raise RuntimeError("Chirp3 API failed to generate any audio files.")

        return (audio_data,)


NODE_CLASS_MAPPINGS = {"Chirp3TextToAudioNode": Chirp3TextToAudioNode}
NODE_DISPLAY_NAME_MAPPINGS = {"Chirp3TextToAudioNode": "Chirp 3 Text To Audio"}
