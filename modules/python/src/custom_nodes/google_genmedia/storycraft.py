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

# Storycraft
import json
import yaml
import time
from typing import Optional

from google import genai
from google.genai import types

from . import exceptions,  storycraft_prompt
from .config import GoogleGenAIBaseAPI
from .constants import (
    STORYCRAFT_USER_AGENT,
    GeminiModel,
    Imagen4Model,
    Veo3Model,
)
from .retry import retry_on_api_error

STYLES = {
    "2D Animation Styles": ["Classic / Traditional", "Anime / Manga"],
    "3D Animation Styles": ["Stylized Realism (Pixar-like)"],
}
flat_style_list = [style for category in STYLES.values() for style in category]
LANGUAGES = ["en-US", "es-US", "fr-FR", "de-DE", "ja-JP"]


class StoryCraft(GoogleGenAIBaseAPI):
    """
    A single, combined ComfyUI node that encapsulates the entire StoryCraft pipeline,
    from scenario generation to final video stitching.
    """

    def __init__(self):
        """
        Initializes the Gemini client.
        """
        self.client = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pitch": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A lone astronaut discovers a mysterious, glowing plant on an otherwise barren moon.",
                    },
                ),
                "num_scenes": ("INT", {"default": 1, "min": 1, "max": 20}),
                "style": (flat_style_list,),
                "language": (LANGUAGES,),
                "output_gcs_uri": ("STRING", {"default": ""}),
                "tts_model_voice": (
                    "STRING",
                    {"multiline": False, "default": "en-US-Studio-O"},
                ),
                "generation_model": (
                    [model.name for model in GeminiModel],
                    {"default": GeminiModel.GEMINI_PRO.name},
                ),
                "image_model": (
                    [model.name for model in Imagen4Model],
                    {"default": Imagen4Model.IMAGEN_4_PREVIEW.name},
                ),
                "video_model": (
                    [model.name for model in Veo3Model],
                    {"default": Veo3Model.VEO_3_PREVIEW.name},
                ),
                "lyria_model": ("STRING", {"multiline": False, "default": "lyria-002"}),
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
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("FINAL_VIDEO_URI",)
    FUNCTION = "run_full_pipeline"
    CATEGORY = "Google AI/Storycraft"

    def run_full_pipeline(
        self,
        pitch,
        num_scenes,
        style,
        language,
        output_gcs_uri,
        tts_model_voice,
        generation_model,
        image_model,
        video_model,
        lyria_model,
        temperature: float,
        max_output_tokens: int,
        top_p: float,
        top_k: int,
        gcp_project_id: str = "",
        gcp_region: str = "",
    ):
        print("--- Starting Full StoryCraft Pipeline ---")
        try:
            GoogleGenAIBaseAPI.__init__(
                self,
                project_id=gcp_project_id or None,
                region=gcp_region or None,
                user_agent=STORYCRAFT_USER_AGENT,
            )
        except exceptions.APIInitializationError as e:
            print(f"Failed to initialize Gemini client: {e}")
            raise RuntimeError(f"Failed to initialize Gemini client: {e}") from e

        try:
            # 1. Generate Scenario Blueprint
            print("Generate scan")
            scenario_blueprint_str = self._generate_scenario(
                self=self,
                pitch=pitch,
                num_scenes=num_scenes,
                style=style,
                language=language,
                model_name=generation_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_p=top_p,
                top_k=top_k,
            )
            return scenario_blueprint_str
            """
            if not scenario_blueprint_str or "error" in scenario_blueprint_str:
                raise ValueError("Failed to generate scenario blueprint.")

            # 2. Generate Character Sheets
            scenario_with_images_str = self._generate_character_sheets(
                scenario_blueprint_str, gcs_bucket_uri, image_model
            )
            if not scenario_with_images_str or "error" in scenario_with_images_str:
                raise ValueError("Failed to generate character sheets.")

            # 3. Generate Storyboard
            full_scenario_str = self._generate_storyboard(
                scenario_with_images_str, num_scenes, style, generation_model
            )
            if not full_scenario_str or "error" in full_scenario_str:
                raise ValueError("Failed to generate storyboard.")

            full_scenario = json.loads(full_scenario_str)

            # 4. Process Each Scene
            all_video_clips = []
            all_voiceovers = []
            music_uri = ""

            scenes = full_scenario.get("scenes", [])
            if not scenes:
                raise ValueError("No scenes were generated in the storyboard.")

            for i, scene in enumerate(scenes):
                print(f"--- Processing Scene {i+1} ---")

                _, image_prompt_str, video_prompt_str, voiceover_text = (
                    self._select_scene(full_scenario_str, i)
                )

                video_clip_uri = self._generate_scene_video(
                    full_scenario_str,
                    image_prompt_str,
                    video_prompt_str,
                    gcs_bucket_uri,
                    image_model,
                    video_model,
                )
                if not video_clip_uri or "error" in video_clip_uri:
                    print(
                        f"Warning: Failed to generate video for scene {i+1}. Skipping."
                    )
                    continue
                all_video_clips.append(video_clip_uri)

                voiceover_uri, music_uri = self._generate_audio(
                    full_scenario_str,
                    voiceover_text,
                    gcs_bucket_uri,
                    tts_model_voice,
                    lyria_model,
                )
                if voiceover_uri and "error" not in voiceover_uri:
                    all_voiceovers.append(voiceover_uri)

            if not all_video_clips:
                raise ValueError("Video generation failed for all scenes.")

            # 5. Stitch Final Video
            final_video_uri = self._stitch_video(
                all_video_clips, all_voiceovers, music_uri, gcs_bucket_uri
            )

            print(
                f"--- Full StoryCraft Pipeline Complete. Final Video URI: {final_video_uri} ---"
            )
            return (final_video_uri,)
            """

        except Exception as e:
            print(f"An error occurred during the pipeline: {e}")
            # return (f"{gcs_bucket_uri}/error.mp4",)

    #@retry_on_api_error()
    def _generate_scenario(
        self,
        pitch: str,
        num_scenes: int,
        style: str,
        language: str,
        model_name: str,
        temperature: float,
        max_output_tokens: int,
        top_p: float,
        top_k: int,
    ):
        print(f"Generating scenario blueprint with model: {model_name}...")
        prompt = storycraft_prompt.get_scenario_prompt(
            pitch, num_scenes, style, language
        )
        print(prompt)
        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k,
            response_mime_type="application/json",
        )
        print(gen_config)
        print(f"Generating text with model: {model_name}")
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                generation_config=gen_config,
            )

            if response and response.text:
                print(response.text)
                return response.text
            else:
                raise exceptions.APICallError("API call for scenario generation returned no text.")

        except Exception as e:
            print(f"An unexpected error occurred during text generation: {e}")
            raise exceptions.APICallError(f"Text generation failed: {e}") from e

    def _generate_character_sheets(
        self, SCENARIO_BLUEPRINT: str, gcs_bucket_uri: str, model_name: str
    ):
        print(f"Generating character sheets with model: {model_name}...")
        try:
            scenario_data = json.loads(SCENARIO_BLUEPRINT)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})

        style = scenario_data.get("style", "cinematic")

        for item_type in ["characters", "settings", "props"]:
            if item_type in scenario_data and isinstance(
                scenario_data[item_type], list
            ):
                for item in scenario_data[item_type]:
                    shot_type = (
                        "Medium Shot"
                        if item_type == "characters"
                        else "Wide Shot"
                        if item_type == "settings"
                        else "Close Shot"
                    )
                    aspect_ratio = "1:1" if item_type != "settings" else "16:9"
                    item["imageGcsUri"] = self._generate_single_image(
                        item_name=item.get("name", f"unknown-{item_type}"),
                        item_description=item.get("description", ""),
                        style=style,
                        shot_type=shot_type,
                        aspect_ratio=aspect_ratio,
                        gcs_bucket_uri=gcs_bucket_uri,
                        model_name=model_name,
                    )
        return json.dumps(scenario_data, indent=4)

    def _generate_single_image(
        self,
        item_name: str,
        item_description: str,
        style: str,
        shot_type: str,
        aspect_ratio: str,
        gcs_bucket_uri: str,
        model_name: str,
    ):
        prompt_data = {
            "style": style,
            "shot_type": shot_type,
            "description": item_description,
        }
        prompt_string = yaml.dump(prompt_data, indent=2, default_flow_style=False)
        sanitized_name = item_name.lower().replace(" ", "-")
        image_gcs_uri = f"{gcs_bucket_uri}/mock-images/{sanitized_name}.png"
        return image_gcs_uri

    def _generate_storyboard(
        self, SCENARIO_WITH_IMAGES: str, num_scenes: int, style: str, model_name: str
    ):
        print(f"Generating storyboard scenes with model: {model_name}...")
        try:
            scenario_data = json.loads(SCENARIO_WITH_IMAGES)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})

        prompt = storycraft_prompt.get_scenes_prompt(scenario_data, num_scenes, style)
        # This is a placeholder for a real API call
        mock_response_text = """
        {
            "scenes": [
                {
                    "imagePrompt": {
                        "Style": "Cinematic, high-contrast, realistic",
                        "Scene": "The first frame shows Dr. Eva Rostova inside her helmet, her eyes wide with awe, reflecting the glow of the alien plant.",
                        "Composition": {
                            "shot_type": "Extreme Close-up on Eva's face",
                            "lighting": "Soft blue light from the plant illuminating her face in the darkness of space",
                            "overall_mood": "Awe and wonder"
                        },
                        "Subject": [{"name": "Dr. Eva Rostova"}],
                        "Prop": [],
                        "Context": [{"name": "Lunar Surface"}]
                    }
                    ,
                    "videoPrompt": {
                        "Action": "Dr. Eva Rostova slowly reaches out a gloved hand towards the glowing plant. The plant pulses with light as her finger gets closer.",
                        "Camera_Motion": "Static, fixed on the interaction.",
                        "Ambiance_Audio": "The low hum of the suit's life support, the soft crackle of radio static.",
                        "Dialogue": []
                    },
                    "description": "Eva, mesmerized by the discovery, cautiously extends her hand to touch the mysterious plant.",
                    "voiceover": "In the unending silence of space, a single, impossible spark of life appeared.",
                    "charactersPresent": ["Dr. Eva Rostova"]
                }
            ]
        }
        """
        try:
            scenes_data = json.loads(mock_response_text)
            scenario_data["scenes"] = scenes_data.get("scenes", [])
        except json.JSONDecodeError:
            scenario_data["scenes"] = []

        return json.dumps(scenario_data, indent=4)

    def _select_scene(self, FULL_SCENARIO: str, scene_index: int):
        print(f"Selecting scene at index: {scene_index}")
        try:
            scenario_data = json.loads(FULL_SCENARIO)
        except json.JSONDecodeError:
            return (
                FULL_SCENARIO,
                "{}",
                "{}",
                "",
            )

        scenes = scenario_data.get("scenes", [])

        if not scenes or not isinstance(scenes, list) or scene_index >= len(scenes):
            return (
                FULL_SCENARIO,
                "{}",
                "{}",
                "",
            )

        selected_scene = scenes[scene_index]

        image_prompt_obj = selected_scene.get("imagePrompt", {})
        video_prompt_obj = selected_scene.get("videoPrompt", {})
        voiceover_text = selected_scene.get("voiceover", "")

        image_prompt_str = json.dumps(image_prompt_obj, indent=4)
        video_prompt_str = json.dumps(video_prompt_obj, indent=4)

        return (FULL_SCENARIO, image_prompt_str, video_prompt_str, voiceover_text)

    def _generate_scene_video(
        self,
        FULL_SCENARIO_PASSTHROUGH,
        IMAGE_PROMPT,
        VIDEO_PROMPT,
        gcs_bucket_uri,
        image_model,
        video_model,
    ):
        print("--- Starting Scene Video Generation ---")
        try:
            full_scenario = json.loads(FULL_SCENARIO_PASSTHROUGH)
            image_prompt_data = json.loads(IMAGE_PROMPT)
            video_prompt_data = json.loads(VIDEO_PROMPT)
        except json.JSONDecodeError as e:
            return f"{gcs_bucket_uri}/error.mp4"

        scene_keyframe_uri = self._generate_keyframe_image(
            full_scenario, image_prompt_data, gcs_bucket_uri, image_model
        )

        if "error" in scene_keyframe_uri:
            return f"{gcs_bucket_uri}/error.mp4"

        video_clip_uri = self._generate_video_clip(
            scene_keyframe_uri,
            video_prompt_data,
            full_scenario,
            gcs_bucket_uri,
            video_model,
        )

        return video_clip_uri

    def _generate_keyframe_image(
        self, full_scenario, image_prompt_data, gcs_bucket_uri, model_name
    ):
        subjects = image_prompt_data.get("Subject", [])
        character_uris = []
        for subject in subjects:
            char_name = subject.get("name")
            for character in full_scenario.get("characters", []):
                if character.get("name") == char_name:
                    if "imageGcsUri" in character:
                        character_uris.append(character["imageGcsUri"])

        prompt_parts = []
        for uri in character_uris:
            prompt_parts.append(f"[Image from: {uri}]")

        text_prompt = yaml.dump(image_prompt_data, indent=2, default_flow_style=False)
        prompt_parts.append(text_prompt)

        keyframe_uri = (
            f"{gcs_bucket_uri}/scene_keyframes/mock_keyframe_{time.time()}.png"
        )
        return keyframe_uri

    def _generate_video_clip(
        self, keyframe_uri, video_prompt_data, full_scenario, gcs_bucket_uri, model_name
    ):
        video_text_prompt = f"""Action: {video_prompt_data.get("Action", "")}Camera Motion: {video_prompt_data.get("Camera_Motion", "")}"""
        aspect_ratio = full_scenario.get("aspectRatio", "16:9")
        duration_seconds = full_scenario.get("durationSeconds", 8)

        video_uri = f"{gcs_bucket_uri}/video_clips/mock_clip_{time.time()}.mp4"
        return video_uri

    def _generate_audio(
        self,
        FULL_SCENARIO_PASSTHROUGH,
        VOICEOVER_TEXT,
        gcs_bucket_uri,
        tts_model_voice,
        lyria_model,
    ):
        print("--- Starting Audio Generation ---")
        try:
            full_scenario = json.loads(FULL_SCENARIO_PASSTHROUGH)
        except json.JSONDecodeError as e:
            return (
                f"{gcs_bucket_uri}/error.mp3",
                f"{gcs_bucket_uri}/error.mp3",
            )

        voiceover_uri = self._generate_voiceover(
            VOICEOVER_TEXT, full_scenario, gcs_bucket_uri, tts_model_voice
        )
        music_uri = self._generate_music(full_scenario, gcs_bucket_uri, lyria_model)

        return (voiceover_uri, music_uri)

    def _generate_voiceover(
        self, voiceover_text, full_scenario, gcs_bucket_uri, tts_model_voice
    ):
        if not voiceover_text.strip():
            return ""

        language = full_scenario.get("language", {}).get("code", "en-US")
        voiceover_gcs_uri = (
            f"{gcs_bucket_uri}/voiceovers/mock_voiceover_{time.time()}.mp3"
        )
        return voiceover_gcs_uri

    def _generate_music(self, full_scenario, gcs_bucket_uri, lyria_model):
        music_prompt = full_scenario.get(
            "music", "A gentle, swelling orchestral piece."
        )
        music_gcs_uri = f"{gcs_bucket_uri}/music/mock_music_{time.time()}.mp3"
        return music_gcs_uri

    def _stitch_video(
        self,
        video_clip_uris: list,
        voiceover_uris: list,
        music_uri: str,
        gcs_bucket_uri: str,
    ):
        print(f"--- Assembling video from {len(video_clip_uris)} clips ---")
        # This is a placeholder for a real video stitching implementation that would
        # download, concatenate, and mix the assets before re-uploading.
        final_gcs_uri = f"{gcs_bucket_uri}/final_videos/final_movie_{time.time()}.mp4"
        return final_gcs_uri


NODE_CLASS_MAPPINGS = {"StoryCraft": StoryCraft}

NODE_DISPLAY_NAME_MAPPINGS = {"StoryCraft": "StoryCraft"}
