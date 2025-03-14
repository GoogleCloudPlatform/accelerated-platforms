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
import logging
import logging.config
import os

import aiohttp
import backoff

# Define the API Endpoints
TEXT_API_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT_TEXT")
IMAGE_API_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT_IMAGE")
MULTIMODAL_API_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT_MULTIMODAL")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
    )
    logger.setLevel(new_log_level)


# Log endpoint URLs *after* the log level is potentially set by the environment
logger.info("Available embedding endpoints...")
logger.info("Text Embedding endpoint: %s", TEXT_API_ENDPOINT)
logger.info("Image Embedding endpoint: %s", IMAGE_API_ENDPOINT)
logger.info("Multimodal Embedding endpoint: %s", MULTIMODAL_API_ENDPOINT)


@backoff.on_exception(
    exception=(aiohttp.ClientError, asyncio.TimeoutError),
    max_tries=3,
    wait_gen=backoff.expo,
)
async def get_embeddings_async(
    session: aiohttp.ClientSession,
    image_uri: str | None = None,
    text: str | None = None,
    timeout_settings: aiohttp.ClientTimeout | None = None,
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
            url,
            json=payload,
            headers=headers,
            timeout=timeout_settings,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(
                    "Error calling embedding API. Status: %s, URL: %s, Payload: %s,  Error: %s",
                    response.status,
                    url,
                    payload,
                    error_text,
                )
                response.raise_for_status()

            data = await response.json()

            if image_uri and text:
                return data.get("multimodal_embeds")
            elif text:
                return data.get("text_embeds")
            elif image_uri:
                return data.get("image_embeds")

    except aiohttp.ClientError:
        logger.exception("ClientError during embedding generation")
        raise


async def get_embeddings(
    image_uri: str | None = None,
    text: str | None = None,
    timeout_settings: aiohttp.ClientTimeout | None = None,
):
    """Asynchronously fetch embeddings"""
    async with aiohttp.ClientSession() as session:
        embeddings = await get_embeddings_async(
            image_uri=image_uri,
            session=session,
            text=text,
            timeout_settings=timeout_settings,
        )
        return embeddings
