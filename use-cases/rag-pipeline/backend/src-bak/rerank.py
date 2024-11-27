# Copyright 2024 Google LLC
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
import requests

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("backend")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)

gemma_it_endpoint = os.getenv("IT_MODEL")  # rag-it-model-l4"

namespace = os.getenv("MLP_KUBERNETES_NAMESPACE")

url = f"http://{gemma_it_endpoint}.{namespace}:8000/v1/chat/completions"

headers = {"Content-Type": "application/json"}


def query_pretrained_gemma(prompt):
    """
    Sends a request to the VLLM endpoint for text completion.

    Args:
      prompt: The text prompt for the model.

    Returns:
      The generated text response from the VLLM model.
    """
    data = {
        "model": "google/gemma-2-2b-it",
        "messages": [{"role": "user", "content": f"{prompt}"}],
        "temperature": 0.7,  # Lowered temperature to make it more deterministic and focused
        "max_tokens": 384,  # Increased max_tokens
        "top_p": 1.0,
        "top_k": 1.0,
    }

    response = requests.post(url, headers=headers, json=data)
    # logging.info(response.json())
    response.raise_for_status()  # Raise an exception for error responses

    # return response.json()["choices"][0]["text"]
    return response.json()["choices"][0]["message"]["content"]
