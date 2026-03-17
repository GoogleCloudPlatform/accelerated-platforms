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

import logging
import logging.config
import os
import sys
from typing import Any, Dict, List, Optional, Set, Union

import gradio as gr
import httpx

# Configure a high-performance async client
http_client: httpx.AsyncClient = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=None, max_connections=None),
    timeout=60.0,
)


class LLMGradioApp:
    """A high-performance Gradio application for interfacing with LLM Gateways."""

    def __init__(self, config_path: str = "logging.conf") -> None:
        """Initialize the application: setup logging, environment variables,
        and security configurations.

        Args:
            config_path: Path to the logging configuration file.
        """
        self.logger: logging.Logger = self._setup_logging(config_path)
        self.gateway_url: str = os.getenv("GATEWAY_URL", "http://localhost:8000")

        self.static_model_list: List[str] = [
            "google/gemma-3-1b-it",
            "google/gemma-3-4b-it",
            "google/gemma-3-27b-it",
            "openai/gpt-oss-20b",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen3-32b",
        ]

        self.model: str = os.getenv("MODEL", "qwen/qwen3-32B")
        if self.model not in self.static_model_list:
            self.static_model_list.append(self.model)

        self.allowed_models: Set[str] = set(self.static_model_list)
        self.request_timeout: int = 30

        if self.gateway_url == "http://localhost:8000":
            self.logger.warning("GATEWAY_URL not set. Defaulting to localhost.")
        self.logger.info(f"App initialized. Gateway: {self.gateway_url}")

    def _setup_logging(self, config_path: str) -> logging.Logger:
        """Helper to load logging configuration safely.

        Args:
            config_path: Path to the logging configuration file.

        Returns:
            A configured logging.Logger instance.
        """
        try:
            # disable_existing_loggers=False is vital for Gradio compatibility
            logging.config.fileConfig(config_path, disable_existing_loggers=False)
            return logging.getLogger("root")
        except Exception as e:
            # Fallback logger if file is missing
            print(f"Failed to load {config_path}: {e}", file=sys.stderr)
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("fallback")

    def _parse_history(
        self, history: List[Union[List[str], Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """Normalizes Gradio history into the OpenAI messages format.

        Args:
            history: The chat history provided by Gradio, either as a list of lists
                or a list of dictionaries.

        Returns:
            A list of dictionaries in the format [{"role": "...", "content": "..."}].
        """
        messages_payload: List[Dict[str, str]] = []
        if not history:
            return messages_payload

        for turn in history:
            if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                messages_payload.append({"role": "user", "content": str(turn[0])})
                messages_payload.append({"role": "assistant", "content": str(turn[1])})
            elif isinstance(turn, dict):
                # Handle cases where history might already be dicts
                messages_payload.append(turn)
        return messages_payload

    async def chat(
        self,
        message: str,
        history: List[Any] = [],
        model_selector: str = "Qwen/Qwen3-32B",
    ) -> str:
        """Core logic handler for the chat interface.

        Sends the user message and history to the LLM gateway.

        Args:
            message: The current user input string.
            history: The previous conversation turns.
            model_selector: The string ID of the model to use for inference.

        Returns:
            The text response from the LLM or an error message.
        """
        if not message:
            return ""

        if model_selector not in self.allowed_models:
            self.logger.error(
                "Security: Invalid model selector", extra={"model": model_selector}
            )
            return "Error: Invalid model selection."

        # Build Payload
        messages_payload = self._parse_history(history)
        messages_payload.append({"role": "user", "content": message})

        payload: Dict[str, Any] = {
            "model": model_selector,
            "messages": messages_payload,
        }

        self.logger.info(
            "Sending request",
            extra={"model": model_selector, "context_length": len(messages_payload)},
        )

        try:
            # Non-blocking request
            resp = await http_client.post(
                f"{self.gateway_url}/v1/chat/completions",
                json=payload,
                timeout=self.request_timeout,
            )

            if resp.status_code == 200:
                self.logger.info("Request success", extra={"status": 200})
                return (
                    resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            else:
                self.logger.error(
                    "Backend Error",
                    extra={"status": resp.status_code, "response": resp.text},
                )
                return f"Error: Backend responded with {resp.status_code}"

        except Exception:
            self.logger.exception("Unexpected exception in chat handler")
            return "An unexpected error occurred."

    def build_ui(self) -> gr.Blocks:
        """Constructs the Gradio UI Blocks.

        Returns:
            A gr.Blocks object containing the application layout.
        """
        with gr.Blocks(title="High Performance LLM Interface") as chat_ui:
            gr.Markdown("## Chat Interface")

            # UI Components for API/Backend interaction
            api_msg = gr.Textbox(visible=False)
            api_hist = gr.State(value=[])
            api_model = gr.Dropdown(choices=list(self.allowed_models), visible=False)
            api_output = gr.Textbox(visible=False)
            btn = gr.Button(visible=False)

            btn.click(
                fn=self.chat,
                inputs=[api_msg, api_hist, api_model],
                outputs=[api_output],
                api_name="sync_chat",
                queue=False,
                concurrency_limit=None,
            )

            # Standard Chat Interface for human users
            gr.ChatInterface(
                fn=self.chat,
                additional_inputs=[
                    gr.Dropdown(choices=list(self.allowed_models), value=self.model)
                ],
            )

        return chat_ui

    def launch(self, server_name: str = "0.0.0.0", server_port: int = 7860) -> None:
        """Launches the Gradio application.

        Args:
            server_name: The network address to listen on.
            server_port: The port to bind the server to.
        """
        chat_ui = self.build_ui()
        chat_ui.queue(default_concurrency_limit=None)
        chat_ui.launch(
            server_name=server_name, server_port=server_port, max_threads=1000
        )


if __name__ == "__main__":
    app = LLMGradioApp()
    app.launch()
