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

from typing import Any, Dict, Optional, Tuple, List


from .constants import LYRIA2_MAX_SAMPLES, MAX_SEED
from .custom_exceptions import APIExecutionError, APIInputError, ConfigurationError
from .lyria2_api import Lyria2API


class Lyria2TextToMusicNode:
    """A ComfyUI node for generating music from text prompts using the Google Lyria 2 API."""

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
                        "placeholder": "Describe the music you want to generate...",
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

    RETURN_TYPES = ("LYRIA_AUDIO",)
    RETURN_NAMES = ("audio_paths",)
    FUNCTION = "generate_music"
    CATEGORY = "Google AI/Lyria2"

    def generate_music(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        sample_count: int = 1,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[List[str],]:
        """
        Generates music from a text prompt using the Lyria 2 API.

        Args:
            prompt: The text prompt for music generation.
            negative_prompt: An optional prompt to guide the model to avoid generating certain things.
            seed: An optional seed for reproducible music generation.
            sample_count: The number of music samples to generate.
            gcp_project_id: The GCP project ID. If provided, overrides metadata lookup.
            gcp_region: The GCP region. If provided, overrides metadata lookup.

        Returns:
            A tuple containing a list of file paths to the generated music.

        Raises:
            ConfigurationError: If input parameters are invalid or GCP configuration is missing.
            RuntimeError: If music generation fails due to API errors or unexpected issues.
        """

        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ConfigurationError("Prompt cannot be empty.")

        if seed != 0 and sample_count > 1:
            raise ConfigurationError(
                "Cannot use a specific 'seed' and 'sample_count' > 1 in the same request."
            )

        if not (1 <= sample_count <= LYRIA2_MAX_SAMPLES):
            raise ConfigurationError(
                f"sample_count must be between 1 and {LYRIA2_MAX_SAMPLES}."
            )

        try:
            lyria2_api = Lyria2API(project_id=gcp_project_id, region=gcp_region)
            audio_paths = lyria2_api.generate_music_from_text(
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                sample_count=sample_count,
            )
        except APIInputError as e:
            raise RuntimeError(f"Input Error: {e}") from e
        except APIExecutionError as e:
            raise RuntimeError(f"API Error: {e}") from e
        except ConfigurationError as e:
            raise RuntimeError(f"Configuration Error: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred during music generation: {e}"
            ) from e
        if not audio_paths:
            raise RuntimeError("Lyria API failed to generate any audio files.")

        return (audio_paths,)


NODE_CLASS_MAPPINGS = {"Lyria2TextToMusicNode": Lyria2TextToMusicNode}
NODE_DISPLAY_NAME_MAPPINGS = {"Lyria2TextToMusicNode": "Lyria 2 Text To Music"}
