# -*- coding: utf-8 -*-
"""
This script creates a ComfyUI custom node to generate audio using
Google Cloud Text-to-Speech Chirp 3 HD voices.

It imports the `Chirp3API` class from `chirp3_api.py`
and correctly parses its dictionary output.

Refactored to follow the design pattern of Lyria2TextToMusicNode.
"""

import torch
from typing import Optional, Tuple

# --- Import the API wrapper ---
# This assumes chirp3_api.py is in the same directory
try:
    from .chirp3_api import Chirp3API, ConfigurationError, APIExecutionError
    from . import utils
except ImportError:
    print("Error: Could not import Chirp3API or custom exceptions from chirp3_api.py.")
    print("Please make sure `chirp3_api.py` is in the same directory.")
    Chirp3API = None

    # Define dummy exceptions if import fails so the file can load
    class ConfigurationError(Exception):
        pass

    class APIExecutionError(Exception):
        pass


# --- Import ComfyUI specific modules ---
try:
    import folder_paths
except ImportError:
    print(
        "Could not import folder_paths. Make sure this file is in ComfyUI/custom_nodes/"
    )

# --- Lists for ComfyUI dropdowns ---

CHIRP_VOICE_LIST = [
    "Aoede",
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Leda",
    "Orus",
    "Zephyr",
]

CHIRP_LANGUAGE_LIST = [
    "en-US",
    "de-DE",
    "en-AU",
    "en-GB",
    "en-IN",
    "fr-FR",
    "hi-IN",
    "pt-BR",
    "ar-XA",
    "es-ES",
    "fr-CA",
    "id-ID",
    "it-IT",
    "ja-JP",
    "tr-TR",
    "vi-VN",
    "bn-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "ta-IN",
    "te-IN",
    "nl-NL",
    "ko-KR",
    "cmn-CN",
    "pl-PL",
    "ru-RU",
    "th-TH",
]

# --- ComfyUI Node Class ---


class GoogleTTSChirpNode:
    """
    A ComfyUI node to generate speech using Google Cloud's Chirp 3 HD voices.
    Outputs an audio tensor and sample rate.
    """

    def __init__(self):
        self.api_client = None

    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the inputs for the node in the ComfyUI interface.
        """
        return {
            "required": {
                "text": (
                    "STRING",
                    {"multiline": True, "default": "Hello world! I am Chirp 3."},
                ),
                "voice_name": (CHIRP_VOICE_LIST,),
                "language_code": (CHIRP_LANGUAGE_LIST,),
            },
            "optional": {
                "gcp_project_id": (
                    "STRING",
                    {"default": "", "placeholder": "your-gcp-project-id"},
                ),
                "gcp_region": ("STRING", {"default": "", "placeholder": "us-central1"}),
            },
        }

    # Define the output types
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)

    # Define the function name that will be executed
    FUNCTION = "generate_audio_tensor"

    # Define the category for the node
    CATEGORY = "Audio/TTS"

    def generate_audio_tensor(
        self,
        text: str,
        voice_name: str,
        language_code: str,
        gcp_project_id: Optional[str] = None,
        gcp_region: Optional[str] = None,
    ) -> Tuple[dict,]:
        """
        The main execution function of the node.
        """
        if not text or not text.strip():
            raise ConfigurationError("Text prompt cannot be empty.")

        if not Chirp3API:
            raise RuntimeError("Chirp3API is not loaded. Check import errors.")

        # Chirp HD native sample rate
        sample_rate = 24000

        try:
            # 1. Initialize client dynamically
            if self.api_client is None:
                self.api_client = Chirp3API(project_id=gcp_project_id, region=gcp_region)

            # 2. Get the dictionary response from your API
            chirp_output = self.api_client.generate_audio(
                text=text,
                voice_name=voice_name,
                language_code=language_code,
                sample_rate_hertz=sample_rate,
            )

            # 3. Process the response using the new dedicated function
            final_audio = utils.process_speech_response(chirp_output)

            return (final_audio,)

        except (ConfigurationError, APIExecutionError) as e:
            print(f"Error during TTS generation or parsing: {e}")
            # Return a dummy audio tensor on error
            return ({"waveform": torch.empty(0), "sample_rate": 0},)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return ({"waveform": torch.empty(0), "sample_rate": 0},)


# --- ComfyUI Node Mappings ---

# A dictionary that maps class names to display names
NODE_DISPLAY_NAME_MAPPINGS = {
    "GoogleTTSChirpNode": "Google TTS (Chirp)",
}

# A dictionary that maps class names to Python classes
NODE_CLASS_MAPPINGS = {
    "GoogleTTSChirpNode": GoogleTTSChirpNode,
}
