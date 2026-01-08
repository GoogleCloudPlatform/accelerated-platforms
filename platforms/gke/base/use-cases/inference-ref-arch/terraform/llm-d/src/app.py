import logging
import logging.config
import os
import sys

import gradio as gr
import requests

# --- 1. CONFIGURATION & LOGGING SETUP ---
# Configure standard logging (JSON formatting is preferred for Cloud, but this is standard text)
try:
    logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
except Exception as e:
    # Fallback if config file is missing or invalid
    print(f"Failed to load logging.conf: {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("root")  # Matches keys=root in your config

# Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL")
# Security: Whitelist allowed models to prevent injection of unknown model names
ALLOWED_MODELS = {"Qwen/Qwen3-0.6B", "google/gemma-2b", "meta-llama/Llama-2-7b-chat-hf"}
MAX_MESSAGE_LENGTH = 10000  # Security: Prevent massive payloads (DoS)
REQUEST_TIMEOUT = 30  # Security: Prevent hanging connections

if not GATEWAY_URL:
    logger.warning(
        "GATEWAY_URL env var is not set. Defaulting to http://localhost:8000, which may fail in K8s."
    )
    GATEWAY_URL = "http://localhost:8000"

logger.info(f"Starting App. Gateway URL: {GATEWAY_URL}")


def chat(message, history, model_selector):
    """
    Main chat handler.
    args:
        message (str): Current user message
        history (list): Conversation history
        model_selector (str): Selected model
    """
    # --- 2. INPUT VALIDATION & SECURITY ---
    if not message:
        return ""

    if len(message) > MAX_MESSAGE_LENGTH:
        logger.warning(f"User sent message exceeding length limit: {len(message)}")
        return "Error: Message is too long."

    if model_selector not in ALLOWED_MODELS:
        logger.error(
            f"Security Alert: Invalid model selector received: {model_selector}"
        )
        return "Error: Invalid model selection."

    # --- 3. HISTORY PARSING ---
    if history is None:
        history = []

    messages_payload = []

    # Robust History Parsing Logic
    if len(history) > 0:
        first_item = history[0]
        # Case A: List of Lists (Standard Gradio) [['hi', 'hello']]
        if isinstance(first_item, (list, tuple)):
            for turn in history:
                if len(turn) >= 2:
                    messages_payload.append({"role": "user", "content": str(turn[0])})
                    messages_payload.append(
                        {"role": "assistant", "content": str(turn[1])}
                    )
        # Case B: List of Dicts (OpenAI style) [{'role': 'user'}]
        elif isinstance(first_item, dict):
            for turn in history:
                if turn.get("role") in ["user", "assistant"]:
                    messages_payload.append(
                        {"role": turn["role"], "content": turn["content"]}
                    )

    # Append current message
    messages_payload.append({"role": "user", "content": message})

    # --- 4. BACKEND REQUEST ---
    payload = {"model": model_selector, "messages": messages_payload}

    logger.info(
        f"Sending request | Model: {model_selector} | Context Length: {len(messages_payload)}"
    )

    try:
        # Security: Always use a timeout
        resp = requests.post(
            f"{GATEWAY_URL}/v1/chat/completions", json=payload, timeout=REQUEST_TIMEOUT
        )

        if resp.status_code == 200:
            content = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            logger.info("Success: Received 200 OK")
            return content
        else:
            # Log full details for Admin, show generic error to User
            logger.error(
                f"Backend Error | Status: {resp.status_code} | Response: {resp.text}"
            )
            return f"Error: The backend responded with status {resp.status_code}. Please check logs."

    except requests.exceptions.Timeout:
        logger.error(f"Request timed out after {REQUEST_TIMEOUT} seconds.")
        return "Error: Request timed out. The model took too long to respond."
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection failed to {GATEWAY_URL}")
        return "Error: Could not connect to the inference server."
    except Exception as e:
        logger.exception("Unexpected exception occurred")  # Log stack trace
        return "An unexpected error occurred."


# --- 5. UI CONSTRUCTION ---
with gr.Blocks(title="LLM Routing Interface") as demo:
    gr.Markdown("## Intelligent Routing Demo")

    with gr.Row():
        model_dropdown = gr.Dropdown(
            choices=list(ALLOWED_MODELS),
            value="Qwen/Qwen3-0.6B",
            label="Choose Model",
            interactive=True,
        )

    # Note: Using ChatInterface handles the 'history' state management automatically
    gr.ChatInterface(
        fn=chat,
        additional_inputs=[model_dropdown],
        type="messages",  # Optimizes for newer Gradio versions handling dict/list history
    )

if __name__ == "__main__":
    # In production Docker, we listen on 0.0.0.0
    demo.launch(server_name="0.0.0.0", server_port=7860)
