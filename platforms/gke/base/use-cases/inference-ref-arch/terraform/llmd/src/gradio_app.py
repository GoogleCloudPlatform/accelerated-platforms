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

import gradio as gr
import httpx

http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=None, max_connections=None),
    timeout=60.0,
)


class LLMGradioApp:
    def __init__(self, config_path="logging.conf"):
        """
        Initialize the application: setup logging, environment variables,
        and security configurations.
        """
        self.logger = self._setup_logging(config_path)
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        self.allowed_models = {
            "Qwen/Qwen3-0.6B",
            "google/gemma-2b",
            "meta-llama/Llama-2-7b-chat-hf",
        }
        self.request_timeout = 30

        if self.gateway_url == "http://localhost:8000":
            self.logger.warning("GATEWAY_URL not set. Defaulting to localhost.")
        self.logger.info(f"App initialized. Gateway: {self.gateway_url}")

    def _setup_logging(self, config_path):
        """Helper to load logging configuration safely."""
        try:
            # disable_existing_loggers=False is vital for Gradio compatibility
            logging.config.fileConfig(config_path, disable_existing_loggers=False)
            return logging.getLogger("root")
        except Exception as e:
            # Fallback logger if file is missing
            print(f"Failed to load {config_path}: {e}", file=sys.stderr)
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger("fallback")

    def _parse_history(self, history):
        """
        Normalizes Gradio history (list of lists or list of dicts)
        into the OpenAI messages format.
        """
        messages_payload = []
        if not history:
            return messages_payload
        for turn in history:
            if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                messages_payload.append({"role": "user", "content": str(turn[0])})
                messages_payload.append({"role": "assistant", "content": str(turn[1])})
        return messages_payload

    # --- 1. ASYNC HANDLER (Recommended by Docs) ---
    async def chat(self, message, history=[], model_selector="Qwen/Qwen3-0.6B"):
        """
        Core logic handler for the chat interface.
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
        payload = {"model": model_selector, "messages": messages_payload}
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

        except Exception as e:
            self.logger.exception("Unexpected exception in chat handler")
            return "An unexpected error occurred."

    def build_ui(self):
        """Constructs the Gradio UI Blocks."""
        with gr.Blocks(title="High Performance LLM Interface") as chat_ui:
            gr.Markdown("## Chat Interface")

            # UI Components
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
                    gr.Dropdown(
                        choices=list(self.allowed_models), value="Qwen/Qwen3-0.6B"
                    )
                ],
            )

        return chat_ui

    def launch(self, server_name="0.0.0.0", server_port=7860):
        chat_ui = self.build_ui()
        chat_ui.queue(default_concurrency_limit=None)
        chat_ui.launch(
            server_name=server_name, server_port=server_port, max_threads=1000
        )


if __name__ == "__main__":
    app = LLMGradioApp()
    app.launch()
