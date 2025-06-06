import os
import uuid
import json
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..utils.logging_setup import app_logger as logger
from ..adk_service import get_adk_app
from ..models import AgentPrompt, AgentResponse
from ..utils.adk_parser import parse_adk_output_event
from ..config import NUM_IMAGES_TO_GENERATE, NUM_VIDEOS_PER_CALL

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "static")

session_turn_counts: Dict[str, int] = {}


# --- Helper function to filter agent's internal monologue ---
def filter_agent_monologue(text: str) -> str:
    """Removes common internal monologue patterns from the agent's text response."""
    patterns = [
        # General planning/execution statements
        r"Okay, I will generate (?:three|four|\d+) distinct dialogue options for a mysterious NPC who knows about time and fate\.",
        r"I will extract the UUID and integer from the prefixes to use in the tool call\.",
        r"Extracted `root_log_id`: [a-f0-9-]+",
        r"Extracted `turn_id`: \d+",
        r"Now, I will call the `wrapped_dialogue_tool`\.",
        r"Okay, I've generated all \d+ videos and images based on your selection\.",  # Agent's final summary

        # Specific image/video generation confirmations (usually replaced by consolidated summary)
        r"Okay, I've generated \d+ videos for the fourth image \(gs:\/\/gaming-demo\/generated_images\/imagen3_output.*\)",
        r"Okay, I've generated \d+ videos for the third image \(gs:\/\/gaming-demo\/generated_images\/imagen3_output.*\)",
        r"Okay, I've generated \d+ videos for the second image \(gs:\/\/gaming-demo\/generated_images\/imagen3_output.*\)",
        r"Okay, I've generated \d+ videos for the first image \(gs:\/\/gaming-demo\/generated_images\/imagen3_output.*\)",
        r"I have generated \d+ videos based on the dialogue and the provided image, and logged the results\. The GCS paths for the videos are:",
        r"\* gs:\/\/gaming-demo\/generated_videos\/null-\d+-[a-f0-9]+\/\d+\/sample_\d+\.mp4",
        # Specific GCS paths mentioned by agent

        # Agent's internal refusal/clarification
        r"I am designed to work in a strict sequence of first generating images and then videos\. I cannot gene\S*\.",
        r"I am designed to generate images first before generating videos based on the generated images\. Pleas\S*\.",
        r"Here are the three dialogue options generated for the mysterious NPC:",
        # Sometimes redundant, will be handled by final_response_text logic

        # Any other patterns you observe the agent stating its internal process
    ]

    filtered_text = text
    for pattern in patterns:
        filtered_text = re.sub(pattern, "", filtered_text).strip()

    # Remove empty lines that might result from filtering
    filtered_text = "\n".join([line for line in filtered_text.splitlines() if line.strip()])

    return filtered_text.strip()


@router.get("/", response_class=HTMLResponse)
async def serve_index():
    index_html_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_html_path):
        logger.error(f"UI Error: index.html not found at {index_html_path}")
        raise HTTPException(status_code=500, detail=f"UI Error: index.html not found at {index_html_path}")
    return HTMLResponse(content=open(index_html_path, "r").read(), status_code=200)


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/ask_agent", response_model=AgentResponse)
async def ask_agent_api(request: AgentPrompt):
    adk_app_instance = await get_adk_app()

    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    root_log_id_for_this_session = session_id
    session_turn_counts[session_id] = session_turn_counts.get(session_id, 0) + 1
    current_turn_id = session_turn_counts[session_id]

    user_id = "gaming_user_default"

    logger.info(
        f"API Call: /ask_agent (Prompt: '{request.prompt[:100]}...', Session ID: {session_id}, Turn: {current_turn_id}, Content Gen: {request.is_content_generation})")

    # The prompt from the frontend already includes ROOT_LOG_ID.
    # We add TURN_ID here. The Agent's instruction will guide it to parse these.
    message_to_agent_with_ids = f"[ROOT_LOG_ID:{root_log_id_for_this_session}][TURN_ID:{current_turn_id}] {request.prompt}"

    try:
        try:
            await adk_app_instance.create_session(user_id=user_id, session_id=session_id)
            logger.debug(f"Session '{session_id}' for user '{user_id}' created (or re-created).")
        except ValueError as ve:
            logger.debug(
                f"Attempted to create session '{session_id}', got error: {ve}. Assuming it might already exist.")
            await adk_app_instance.get_session(user_id=user_id, session_id=session_id)
            logger.debug(f"Session '{session_id}' for user '{user_id}' confirmed as existing after create attempt.")
        except Exception as e:
            logger.exception(f"General error during session creation/check for '{session_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error while interacting with agent: {e}")

        final_response_text = ""
        overall_tool_outputs_from_stream: List[Dict[str, Any]] = []  # Renamed for clarity in this fix

        logger.info(f"Sending prompt to ADK agent for processing: {message_to_agent_with_ids[:100]}...")
        async for output_event_dict in adk_app_instance.async_stream_query(
                message=message_to_agent_with_ids,
                user_id=user_id,
                session_id=session_id
        ):
            current_event_text, current_event_tool_outputs = parse_adk_output_event(output_event_dict)

            if current_event_text:
                filtered_chunk = filter_agent_monologue(current_event_text)
                if filtered_chunk:
                    final_response_text += filtered_chunk + "\n"

            if current_event_tool_outputs:
                for tool_output in current_event_tool_outputs:
                    logger.info(
                        f"Received TOOL OUTPUT from ADK stream: Name='{tool_output.get('tool_name')}', Output='{json.dumps(tool_output.get('tool_output'), default=str)}'")

            overall_tool_outputs_from_stream.extend(current_event_tool_outputs)  # Use the renamed accumulator

        logger.info(f"ADK Agent processing completed. Raw response text: {final_response_text[:200]}...")
        logger.info(
            f"Final collected overall_tool_outputs_from_stream: {json.dumps(overall_tool_outputs_from_stream, indent=2, default=str)}")  # CRUCIAL LOG

        # --- CONSOLIDATE TOOL OUTPUTS FOR FRONTEND RESPONSE ---
        # This list will be populated with tool outputs formatted for the frontend
        # and then wrapped into the 'all_tool_outputs' key for the AgentResponse.
        final_tool_outputs_for_frontend_array: List[Dict[str, Any]] = []

        final_image_urls: List[str] = []
        final_video_urls: List[str] = []

        for tool_output_event in overall_tool_outputs_from_stream:  # Iterate through the collected raw events
            tool_name = tool_output_event.get('tool_name')
            tool_output_data = tool_output_event.get('tool_output')

            # Dialogue Tool Output
            if tool_name == 'wrapped_dialogue_tool' and tool_output_data and 'result' in tool_output_data:
                final_tool_outputs_for_frontend_array.append({
                    "tool_name": "generate_and_log_npc_dialogue_tool",  # Frontend expects this specific name
                    "tool_output": {"result": tool_output_data['result']}
                })
            # Image Tool Output
            elif tool_name == 'wrapped_image_tool' and tool_output_data and 'result' in tool_output_data:
                final_image_urls.extend(tool_output_data['result'])
                final_tool_outputs_for_frontend_array.append({
                    "tool_name": "generate_and_log_images_tool",  # Frontend expects this specific name
                    "tool_output": {"result": tool_output_data['result']}
                })
            # Orchestrated Video Tool Output
            elif tool_name == 'wrapped_orchestrate_video_generation_tool' and tool_output_data and 'result' in tool_output_data:
                if isinstance(tool_output_data.get('result'), list):  # Ensure result is a list
                    final_video_urls.extend(tool_output_data['result'])
                    final_tool_outputs_for_frontend_array.append({
                        "tool_name": "generate_and_log_video_tool",  # Frontend expects this specific name
                        "tool_output": tool_output_data['result']
                    })
                else:
                    logger.warning(
                        f"Orchestrated video tool output 'result' was not a list: {tool_output_data.get('result')}")
            # Fallback for individual video tool if it somehow appears directly (less likely with orchestration)
            elif tool_name == 'generate_and_log_video_tool' and tool_output_data:
                if isinstance(tool_output_data, list):
                    final_video_urls.extend(tool_output_data)
                elif isinstance(tool_output_data, str):
                    final_video_urls.append(tool_output_data)
                final_tool_outputs_for_frontend_array.append({
                    "tool_name": "generate_and_log_video_tool",
                    "tool_output": tool_output_data
                })

        final_image_urls = list(set(final_image_urls))
        final_video_urls = list(set(final_video_urls))

        # Prepare the final tool_outputs structure for the AgentResponse model
        final_tool_output_for_response_model: Optional[Dict[str, Any]] = None

        if final_tool_outputs_for_frontend_array:
            final_tool_output_for_response_model = {"all_tool_outputs": final_tool_outputs_for_frontend_array}
        # If final_tool_outputs_for_frontend_array is empty, final_tool_output_for_response_model remains None.

        # Final cleanup and determination of response_text
        final_response_text = "\n".join([line for line in final_response_text.splitlines() if line.strip()]).strip()

        if not final_response_text:
            if any(t.get('tool_name') == 'generate_and_log_npc_dialogue_tool' for t in
                   final_tool_outputs_for_frontend_array):  # Check this new list
                final_response_text = "Here are the generated dialogue options:"
            elif request.is_content_generation:
                final_response_text = f"Successfully generated {len(final_image_urls)} images and {len(final_video_urls)} videos based on your selection."
            else:
                final_response_text = "Agent did not produce a relevant text response, but may have executed tools. See tool outputs for details."

        # Log the exact payload before returning
        response_payload = AgentResponse(
            response_text=final_response_text,
            tool_outputs=final_tool_output_for_response_model,
            session_id=session_id
        ).model_dump_json(indent=2)

        logger.info(f"Returning JSON to frontend: {response_payload[:500]}...")
        logger.debug(f"Full JSON returned to frontend: {response_payload}")

        return AgentResponse(response_text=final_response_text, tool_outputs=final_tool_output_for_response_model,
                             session_id=session_id)

    except Exception as e:
        logger.exception(f"Error in ask_agent_api: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error while interacting with agent: {e}")
