import uuid
import time
import json
from datetime import datetime
import asyncio

from vertexai.preview.generative_models import GenerativeModel, Part
from vertexai.preview.vision_models import ImageGenerationModel
from google.cloud import storage # Synchronous GCS client
from google import genai
from google.genai import types

from . import config
from .config import PROJECT_ID, LOCATION, VIDEO_OUTPUT_GCS_PREFIX, NUM_VIDEOS_PER_CALL
from .game_context_manager import GameContextManager
from .bq_logger import BigQueryLogger

# Initialize Google Cloud Storage synchronous client globally
storage_client = storage.Client(project=config.PROJECT_ID)


# --- Helper Functions for Prompt Building ---
def _build_prompt_for_npc_dialogue_gen(data: dict) -> str:
    """Builds the prompt string for NPC dialogue generation."""
    if not data: return "Error: Game data not provided for prompt generation."
    pcs = "\n".join([f"- {pc['name']}: {pc['description']}" for pc in data.get('player_characters', [])])
    npc_info = data.get('npc', {})
    prompt = f"""
You are an AI writing assistant embedded in a narrative design tool for video games.
Game: {data.get('game_name', 'Unknown Game')}
Setting: {data.get('scene', 'Unknown Setting')}
Characters:
{pcs}
- NPC - {npc_info.get('name', 'Unknown NPC')}: {npc_info.get('description', 'No description.')}
Task: Generate {config.NUM_DIALOGUES_TO_GENERATE} distinct lines of creative, immersive, and lore-rich dialogue for the NPC "{npc_info.get('name', 'Unknown NPC')}" interacting with the player characters.
The dialogue should:
- Reflect the NPC’s strange knowledge of time and fate
- Tease secrets or hidden quests
- Sound unique and characterful
Return the {config.NUM_DIALOGUES_TO_GENERATE} dialogue lines as a numbered list.
"""
    return prompt.strip()

def _build_image_gen_json_from_game_data(data: dict, selected_dialogue: str = "") -> str:
    """
    Constructs a JSON-formatted string representing the game context for image generation.
    It takes the loaded game data and optionally a selected dialogue to embed.
    """
    if not data: return json.dumps({"error": "Game context not available for image prompt."})
    player_chars_for_prompt = []
    for pc in data.get('player_characters', []):
        player_chars_for_prompt.append({"name": pc.get('name', 'Unknown Player Character'),
                                        "description": pc.get('description', 'No description.')})
    npc_info = data.get('npc', {})
    npc_for_prompt = {"name": npc_info.get('name', 'Unknown NPC'),
                      "description": npc_info.get('description', 'No description.'), "dialogue": selected_dialogue}
    image_prompt_data = {
        "game_name": data.get('game_name', 'Unknown Game'),
        "description": data.get('description', 'No game description.'),
        "scene": data.get('scene', 'Unknown Scene.'), "player_characters": player_chars_for_prompt,
        "npc": npc_for_prompt
    }
    return json.dumps(image_prompt_data)


# --- ADK Function Tools (These are the callables for LlmAgent) ---

async def generate_and_log_npc_dialogue_tool(log_id: str, game_context_manager: GameContextManager,
                                       bq_logger: BigQueryLogger) -> list:
    """
    Generates 3 NPC dialogue options, logs to BigQuery, and returns the list.
    The 'log_id' passed here is the ROOT_LOG_ID-TURN_ID from the LLM.
    """
    # Use the log_id as received for BigQuery
    bq_log_id = f"{log_id}-dialogue" # Add a tool-specific suffix for clarity
    game_context = game_context_manager.get_data()
    if not game_context:
        error_msg = "Game context not available for dialogue generation. Check game_data.json."
        print(error_msg)
        bq_logger.log_entry(log_id=bq_log_id, agent_name="npc_dialogue_gen_game_agent",
                            prompt_text_used="Failed to build prompt due to missing game context.",
                            generated_dialogues=[error_msg], task_description="NPC Dialogue Generation (Error)")
        return [error_msg]

    prompt_for_llm = _build_prompt_for_npc_dialogue_gen(game_context)
    print(f"Attempting to generate dialogue with prompt:\n{prompt_for_llm}")

    try:
        model = GenerativeModel(config.GEMINI_FLASH_MODEL)
        response = await asyncio.to_thread(model.generate_content, prompt_for_llm)
        generated_text = response.text.strip()
        dialogue_options = [line.split('. ', 1)[1].strip() for line in generated_text.split('\n') if
                            line.strip() and '. ' in line]
        print(f"Successfully generated Dialogue Options:\n{dialogue_options}")

        bq_logger.log_entry(log_id=bq_log_id, agent_name="npc_dialogue_gen_game_agent", prompt_text_used=prompt_for_llm,
                            generated_dialogues=dialogue_options, task_description="NPC Dialogue Generation")
        return dialogue_options
    except Exception as e:
        error_msg = f"Error during dialogue generation: {e}"
        print(error_msg)
        bq_logger.log_entry(log_id=bq_log_id, agent_name="npc_dialogue_gen_game_agent", prompt_text_used=prompt_for_llm,
                            generated_dialogues=[error_msg], task_description="NPC Dialogue Generation (Error)")
        return [error_msg]


async def generate_and_log_images_tool(log_id: str, game_context_manager: GameContextManager, bq_logger: BigQueryLogger,
                                 selected_dialogue: str) -> list:
    """
    Generates images (NUM_IMAGES_TO_GENERATE), uploads to GCS, and logs. Returns list of GCS paths.
    The 'log_id' passed here is the ROOT_LOG_ID-TURN_ID from the LLM.
    """
    # Use the log_id as received for BigQuery
    bq_log_id = f"{log_id}-image" # Add a tool-specific suffix
    game_context = game_context_manager.get_data()
    generation_model = ImageGenerationModel.from_pretrained(config.IMAGEN_MODEL)
    bucket = storage_client.bucket(config.GCS_BUCKET_NAME)

    image_gcs_paths = []

    updated_image_context_json = _build_image_gen_json_from_game_data(game_context, selected_dialogue)
    final_imagen_prompt = (
        f"Generate an image representing characters and a scene from a video game "
        f"based on the following JSON context, with the NPC speaking the provided dialogue: "
        f"{updated_image_context_json}"
    )

    print(f"Attempting to generate images with prompt:\n{final_imagen_prompt}")

    try:
        response = await asyncio.to_thread(
            generation_model.generate_images,
            prompt=final_imagen_prompt,
            number_of_images=config.NUM_IMAGES_TO_GENERATE,
            aspect_ratio="16:9",
            negative_prompt="text, words, typography, blurry text, overlay, watermark, writing",
            person_generation="allow_adult",
            safety_filter_level="block_few",
            add_watermark=True,
        )

        for i, image in enumerate(response.images):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"imagen3_output_{timestamp}_{uuid.uuid4().hex[:8]}.png"
            blob_name = f"{config.GCS_DESTINATION_BLOB_PREFIX}{unique_filename}"
            blob = bucket.blob(blob_name)

            image_bytes = image._image_bytes
            await asyncio.to_thread(blob.upload_from_string, image_bytes, content_type="image/png")

            gcs_path = f"gs://{config.GCS_BUCKET_NAME}/{blob_name}" # Construct the gs:// path
            image_gcs_paths.append(gcs_path) # Append the gs:// path
            print(f"Image {i + 1} uploaded to {gcs_path}") # Log the gs:// path

        bq_logger.log_entry(
            log_id=bq_log_id, # Use constructed log_id
            agent_name="image_generation_tool",
            prompt_text_used=final_imagen_prompt,
            selected_dialogue=selected_dialogue,
            image_gcs_path=",".join(image_gcs_paths),
            task_description="Image Generation"
        )
        return image_gcs_paths # Return the list of gs:// paths

    except Exception as e:
        error_msg = f"Error during image generation: {e}"
        print(error_msg)
        bq_logger.log_entry(log_id=bq_log_id, agent_name="image_generation_tool", prompt_text_used=final_imagen_prompt,
                            selected_dialogue=selected_dialogue, image_gcs_path="Error",
                            task_description="Image Generation (Error)")
        return []


async def generate_and_log_video_tool(log_id: str, game_context_manager: GameContextManager, bq_logger: BigQueryLogger,
                                selected_dialogue: str, image_gcs_path: str) -> list:
    """
    Generates videos (NUM_VIDEOS_PER_CALL), logs to BigQuery, and returns list of GCS paths.
    The 'log_id' passed here is the ROOT_LOG_ID-TURN_ID-video_base from the LLM.
    """
    game_context = game_context_manager.get_data()
    video_text_prompt = ""
    try:
        video_model = config.VEO_MODEL
        client = genai.Client(vertexai=True, project=config.PROJECT_ID, location=config.LOCATION)

        game_name = game_context.get('game_name', 'a video game')
        scene = game_context.get('scene', 'a fantasy setting')
        npc_name = game_context.get('npc', {}).get('name', 'a mysterious figure')
        game_description = game_context.get('description', 'a world of magic and adventure')

        video_text_prompt = (
            f"Generate a cinematic video sequence for the game '{game_name}'. "
            f"The scene is: '{scene}'. "
            f"The main character, {npc_name}, says: '{selected_dialogue}'. "
            f"The visual style should be consistent with this game's aesthetic, which is '{game_description}'. "
            f"Capture the mood implied by this dialogue. "
            f"Include subtle background audio and the NPC speaking the dialogue."
        )
        print(f"Video generation prompt:\n{video_text_prompt}")

        # The log_id from LLM will be like ROOT_ID-TURN_ID-video
        # Veo's output_gcs_uri is a prefix that Veo itself uses for its internal unique identifiers.
        # So we construct a unique prefix based on the passed log_id.
        unique_video_filename_prefix = f"{log_id}-{uuid.uuid4().hex[:8]}" # Add a unique suffix per VIDEO TOOL CALL
        final_output_gcs_uri = f"{config.VIDEO_OUTPUT_GCS_PREFIX}{unique_video_filename_prefix}/" # Ensure trailing slash

        print(f"Using input image: {image_gcs_path}\nOutputting video to prefix: {final_output_gcs_uri}")

        operation = await asyncio.to_thread(
            client.models.generate_videos,
            model=video_model,
            image=types.Image(
                gcs_uri=image_gcs_path,
                mime_type="image/png",
            ),
            config=types.GenerateVideosConfig(
                aspect_ratio="16:9",
                number_of_videos=NUM_VIDEOS_PER_CALL,
                duration_seconds=8,
                person_generation="allow_adult",
                enhance_prompt=True,
                output_gcs_uri=final_output_gcs_uri # Veo will save to this directory-like prefix
            ),
            prompt=video_text_prompt,
        )

        print(f"Video generation operation started: {operation.name}")

        while not operation.done:
            print("Video generation in progress... waiting 15 seconds.")
            await asyncio.sleep(15)
            operation = client.operations.get(operation)

        video_result = operation.result
        generated_video_gcs_paths = []

        if hasattr(video_result, 'generated_videos') and \
                isinstance(video_result.generated_videos, list) and \
                len(video_result.generated_videos) > 0:

            for video_item in video_result.generated_videos:
                if hasattr(video_item, 'video') and \
                        hasattr(video_item.video, 'uri') and \
                        video_item.video.uri:

                    gs_uri = video_item.video.uri # This is already the gs:// path
                    generated_video_gcs_paths.append(gs_uri) # Append the gs:// path
                    print(f"DEBUG: Appended GCS URI: {gs_uri}")
                else:
                    print(f"WARNING: Video item in list missing 'video.uri' attribute or URI was empty: {video_item}")
        else:
            print("WARNING: Video generation result did not contain valid 'generated_videos' list or it was empty.")
            raise ValueError(
                "Video generation completed without valid video URIs. Content might have been filtered or failed internally.")

        print(
            f"DEBUG: Final list of generated_video_gcs_paths before return: Type={type(generated_video_gcs_paths)}, Value={generated_video_gcs_paths}")

        # Use the passed log_id (ROOT_ID-TURN_ID-video_base) for BQ
        bq_logger.log_entry(
            log_id=f"{log_id}", # The log_id already contains the suffix
            agent_name="video_generation_tool",
            prompt_text_used=video_text_prompt,
            selected_dialogue=selected_dialogue,
            image_gcs_path=image_gcs_path,
            video_gcs_path=",".join(generated_video_gcs_paths),
            task_description="Video Generation"
        )
        return generated_video_gcs_paths

    except Exception as e:
        error_msg = f"ROOT CAUSE ERROR during video generation (generate_and_log_video_tool): {type(e).__name__}: {e}"
        print(error_msg)
        bq_logger.log_entry(log_id=f"{log_id}-error", agent_name="video_generation_tool", prompt_text_used=video_text_prompt,
                            selected_dialogue=selected_dialogue, image_gcs_path=image_gcs_path, video_gcs_path="Error",
                            task_description="Video Generation (Error)")
        raise
