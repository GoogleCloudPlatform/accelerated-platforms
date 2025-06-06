from functools import partial, wraps
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from typing import List  # Import List for type hints

from . import config
from .game_context_manager import GameContextManager
from .bq_logger import BigQueryLogger
from . import content_tools
from .utils.logging_setup import app_logger as logger


async def setup_gaming_agents(game_context_manager: GameContextManager, bq_logger: BigQueryLogger) -> LlmAgent:
    """
    Sets up and returns the root ADK agent with all its sub-agents and tools.
    Dependencies (game_context_manager, bq_logger) are injected into tool functions using functools.partial.
    """

    def create_adk_tool_function(original_tool_func):
        @wraps(original_tool_func)
        async def wrapper_tool_func(*args, **kwargs):
            return await original_tool_func(*args, **kwargs)

        return wrapper_tool_func

    # --- Tool Wrappers ---

    _bound_dialogue_tool_func = partial(
        content_tools.generate_and_log_npc_dialogue_tool,
        game_context_manager=game_context_manager,
        bq_logger=bq_logger
    )

    async def wrapped_dialogue_tool(root_log_id: str, turn_id: str):
        bq_log_id = f"{root_log_id}-{turn_id}"
        return await _bound_dialogue_tool_func(log_id=bq_log_id)

    _bound_image_tool_func = partial(
        content_tools.generate_and_log_images_tool,
        game_context_manager=game_context_manager,
        bq_logger=bq_logger
    )

    async def wrapped_image_tool(dialogue_description: str, root_log_id: str, turn_id: str):
        bq_log_id = f"{root_log_id}-{turn_id}"
        return await _bound_image_tool_func(
            log_id=bq_log_id,
            selected_dialogue=dialogue_description
        )

    # wrapped_video_tool now takes a LIST of image_gcs_paths
    _bound_video_tool_func = partial(
        content_tools.generate_and_log_video_tool,  # This tool will still be called per image
        game_context_manager=game_context_manager,
        bq_logger=bq_logger
    )

    async def wrapped_orchestrate_video_generation_tool(
            dialogue_description: str,
            image_gcs_paths: List[str],  # Expects a list of paths
            root_log_id: str,
            turn_id: str
    ) -> List[str]:  # Returns a flat list of all video GCS paths
        """
        Generates videos for ALL provided image GCS paths, logs to BigQuery, and returns a flat list of all GCS paths.
        This tool internally loops through the images.
        Args:
            dialogue_description (str): The dialogue text or context for video generation.
            image_gcs_paths (List[str]): A list of GCS paths of the images to use for video generation.
        """
        all_generated_video_gcs_paths: List[str] = []

        for i, img_path in enumerate(image_gcs_paths):
            bq_log_id = f"{root_log_id}-{turn_id}-{i}-video"  # Create a unique log_id for each video sub-call
            logger.info(
                f"Calling content_tools.generate_and_log_video_tool for image {i + 1}/{len(image_gcs_paths)}: {img_path}")
            try:
                # Call the underlying content_tools function for each image
                videos_for_this_image = await content_tools.generate_and_log_video_tool(
                    log_id=bq_log_id,
                    game_context_manager=game_context_manager,  # Re-injected by partial 
                    bq_logger=bq_logger,  # Re-injected by partial 
                    selected_dialogue=dialogue_description,
                    image_gcs_path=img_path
                )
                all_generated_video_gcs_paths.extend(videos_for_this_image)
            except Exception as e:
                logger.error(f"Error generating video for image {img_path}: {e}")
                # Decide if you want to re-raise, log, or continue
                # For now, we'll log and continue to try other images
                pass  # Continue to the next image even if one fails

        return all_generated_video_gcs_paths

    # --- Agent Definitions ---

    # Dialogue Agent
    dialogue_agent = LlmAgent(
        name="npc_dialogue_gen_game_agent",
        model=config.GEMINI_FLASH_MODEL,
        description="This agent specializes in generating creative, immersive, and lore-rich NPC dialogue options for the game. It uses pre-configured game data and logs all outputs to BigQuery.",
        instruction=(
            "You are an AI writing assistant embedded in a narrative design tool for video games. "
            f"Your task is to generate exactly {config.NUM_DIALOGUES_TO_GENERATE} distinct NPC dialogue options, each reflecting strange knowledge of time and fate. "
            "Use the 'wrapped_dialogue_tool' to achieve this. "
            "Once the dialogues are generated, present them clearly to the user."
        ),
        tools=[FunctionTool(func=wrapped_dialogue_tool)]
    )

    # Root Agent
    root_agent = LlmAgent(
        name="Coordinator",
        model=config.GEMINI_FLASH_MODEL,
        instruction=(
            f"You are the main AI assistant for game content generation. "
            f"**Your primary task is to fulfill requests for generating dialogues, images, and videos in a strict sequence.**\n"
            f"**Always extract the UUID from the '[ROOT_LOG_ID:UUID]' and integer from '[TURN_ID:N]' prefixes from the prompt.** You MUST pass these `root_log_id` and `turn_id` arguments to all tool calls.\n\n"
            f"**Phase 1: Dialogue Generation**\n"
            f"If the user's prompt is a general request to generate dialogue options, transfer to the 'npc_dialogue_gen_game_agent' to generate {config.NUM_DIALOGUES_TO_GENERATE} NPC dialogue options.\n\n"
            f"**Phase 2: Image and Video Generation (Strict Orchestration)**\n"
            f"If the user's prompt is an orchestration command like 'Orchestrate generation of {config.NUM_IMAGES_TO_GENERATE} images and then {config.NUM_VIDEOS_PER_CALL} videos per image, based on the following dialogue: \"[DIALOGUE_TEXT]\"', then you MUST execute the following steps **exactly once, in this precise order**:\n"
            f"1. **Image Generation:** Call the 'wrapped_image_tool'. The `dialogue_description` argument for this tool MUST be the full dialogue text extracted from the user's prompt.\n"
            f"2. **Combined Video Generation:** IMMEDIATELY after the 'wrapped_image_tool' has *finished executing and provided its list of GCS image paths*, you MUST call the 'wrapped_orchestrate_video_generation_tool' **exactly once**. For this tool call:\n"
            f"   - The `dialogue_description` argument MUST be the same dialogue text that was used for image generation.\n"
            f"   - The `image_gcs_paths` argument MUST be the complete list of GCS image paths returned by the 'wrapped_image_tool'.\n"
            f"**You MUST ensure that all generated outputs (dialogues, images, videos) are logged through their respective tools.**\n"
            f"Once all images and their corresponding videos have been generated and logged by the tools, provide a concise summary of what was created (e.g., 'Generated X images and Y videos for your selected dialogue.'). **DO NOT generate any intermediate text about video generation steps or each video's status, only the final summary.**"
        ),
        description="Main coordinator for game content generation tasks, responsible for orchestrating dialogue, image, and video generation with user selection in between, and ensuring all generated outputs are logged to BigQuery.",
        sub_agents=[dialogue_agent, ],
        tools=[
            FunctionTool(func=wrapped_image_tool),
            FunctionTool(func=wrapped_orchestrate_video_generation_tool)
        ]
    )
    return root_agent
