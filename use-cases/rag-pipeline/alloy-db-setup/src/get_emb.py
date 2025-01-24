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

import asyncio
import json
import logging
import logging.config
import os

import aiohttp
import backoff
import requests

# Define the API Endpoints
TEXT_API_ENDPOINT = os.environ.get("TEXT_EMBEDDING_ENDPOINT")
IMAGE_API_ENDPOINT = os.environ.get("IMAGE_EMBEDDING_ENDPOINT")
MULTIMODAL_API_ENDPOINT = os.environ.get("MULTIMODAL_EMBEDDING_ENDPOINT")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    try:
        # Convert the string to a logging level constant
        numeric_level = getattr(logging, new_log_level)
        # Set the level for the root logger
        logger.setLevel(new_log_level)  # Set the level after getting the logger
        logger.info(
            "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
        )
    except AttributeError:
        logger.warning(
            "Invalid LOG_LEVEL value: '%s'. Using default log level.", new_log_level
        )

# Log endpoint URLs *after* the log level is potentially set by the environment
logger.info("Available embedding endpoints...")
logger.info("Text Embedding endpoint: %s", TEXT_API_ENDPOINT)
logger.info("Image Embedding endpoint: %s", IMAGE_API_ENDPOINT)
logger.info("Multimodal Embedding endpoint: %s", MULTIMODAL_API_ENDPOINT)


@backoff.on_exception(
    backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=3
)
async def get_embeddings_async(
    session, image_uri=None, text=None, timeout_settings=None
):
    """Asynchronously fetches embeddings with retry and error handling."""
    try:
        if image_uri and text:
            url = MULTIMODAL_API_ENDPOINT
            payload = {"image_uri": image_uri, "caption": text}
        elif text:
            url = TEXT_API_ENDPOINT
            payload = {"caption": text}
        elif image_uri:
            url = IMAGE_API_ENDPOINT
            payload = {"image_uri": image_uri}
        else:
            logger.error("No input provided for embedding generation")
            return None

        headers = {"Content-Type": "application/json"}

        async with session.post(
            url, json=payload, headers=headers, timeout=timeout_settings
        ) as response:
            if response.status != 200:  # Explicitly check for non-200 status
                error_text = await response.text()
                logger.error(
                    "Error calling embedding API. Status: %s, URL: %s, Payload: %s,  Error: %s",
                    response.status,
                    url,
                    payload,
                    error_text,
                )  # Include detailed error info
                response.raise_for_status()  # Raise the exception after logging

            data = await response.json()

            if image_uri and text:
                return data.get("multimodal_embeds")
            elif text:
                return data.get("text_embeds")
            elif image_uri:
                return data.get("image_embeds")

    except aiohttp.ClientError as e:
        logger.exception(
            f"Client Error during embedding generation: {e}"
        )  # Log with exception details
        raise  # Re-raise to signal failure to the caller. Handle the backoff at a higher level


async def get_embeddings(image_uri=None, text=None, timeout_settings=None):
    async with aiohttp.ClientSession() as session:
        embeddings = await get_embeddings_async(
            session, image_uri, text, timeout_settings
        )
        return embeddings
