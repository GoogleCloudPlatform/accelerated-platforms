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
logger = logging.getLogger("instruction-tuned-re-ranking")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)

# Construct the URL
# URL = os.environ["GEMMA_IT_ENDPOINT"]
URL = "http://35.222.209.169:8000/v1/chat/completions"


def query_instruction_tuned_gemma(prompt):
    """
    Sends a request to the instruction tuned model endpoint for text completion.

    Args:
        prompt: The text prompt for the model.

    Returns:
        The generated text response from the VLLM model.
    """
    try:
        data = {
            "model": "google/gemma-2-2b-it",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 384,
            "top_p": 1.0,
            "top_k": 1.0,
        }
        response = requests.post(
            URL,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=100,
        )
        print("Printing response from the instruction tuned model:", response.text)
        response.raise_for_status()  # Raise an exception for HTTP errors

        return response.json()["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with instruction model endpoint: {e}")
        print(e)
        return "Error: Could not generate a response."
    except KeyError as e:
        logger.error(f"Unexpected response format from instruction model endpoint: {e}")
        return "Error: Invalid response format."
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return "Error: An unexpected error occurred."
