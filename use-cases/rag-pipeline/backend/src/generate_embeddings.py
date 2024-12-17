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
import json

# Define the API Endpoints for deployment
TEXT_API_ENDPOINT = os.environ.get("TEXT_EMBEDDING_ENDPOINT")
IMAGE_API_ENDPOINT = os.environ.get("IMAGE_EMBEDDING_ENDPOINT")
MULTIMODAL_API_ENDPOINT = os.environ.get("MULTIMODAL_EMBEDDING_ENDPOINT")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("get_embeddings")

logger = logging.getLogger(__name__)
if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    try:
        # Convert the string to a logging level constant
        numeric_level = getattr(logging, new_log_level)

        # Set the level for the root logger
        logging.getLogger().setLevel(numeric_level)

        logger.info(
            "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
        )
        logger.info("Text Embedding endpoint: %s", TEXT_API_ENDPOINT)
        logger.info("Image Embedding endpoint: %s", IMAGE_API_ENDPOINT)
        logger.info("Multimodal Embedding endpoint: %s", MULTIMODAL_API_ENDPOINT)

    except AttributeError:
        logger.warning(
            "Invalid LOG_LEVEL value: '%s'. Using default log level.", new_log_level
        )


def get_image_embeddings(image_uri):
    """
    Fetches image embeddings from an image embedding API.

    Args:
        image_uri: The URI of the image.

    Returns:
        The image embeddings as a JSON object.

    Raises:
        requests.exceptions.HTTPError: If there is an error fetching the image embeddings
                                       or the API returns an invalid response.
    """
    try:
        response = requests.post(
            IMAGE_API_ENDPOINT,
            json={"image_uri": image_uri},
            headers={"Content-Type": "application/json"},
            timeout=100,
        )

        # This will raise an HTTPError for bad responses (4xx or 5xx)
        response.raise_for_status()

        image_embeddings = response.json()["image_embeds"]
        return image_embeddings

    except requests.exceptions.HTTPError as e:
        # Reraise HTTPError for better error handling
        logger.exception("Error fetching image embedding: %s", e)
        raise

    except requests.exceptions.RequestException as e:
        # For other request errors, re-raise as an HTTPError
        logger.exception("Invalid response from image embedding API: %s", e)
        raise requests.exceptions.HTTPError(
            "Error fetching image embedding", response=requests.Response()
        ) from e

    except (ValueError, TypeError) as e:
        # Handle potential JSON decoding errors
        logger.exception(
            "Not able to decode received json from image embedding API: %s", e
        )
        raise requests.exceptions.HTTPError(
            "Invalid response from image embedding API", response=requests.Response()
        ) from e


def get_multimodal_embeddings(image_uri, desc):
    """
    Fetches multimodal embeddings from a multimodal embedding API using text description and image URI.

    Args:
        image_uri: The URI of the image.
        desc: The text description of the product from product catalog.

    Returns:
        The multimodal embeddings as a JSON object.

    Raises:
        requests.exceptions.HTTPError: If there is an error fetching the multimodal embeddings
                                       or the API returns an invalid response.
    """
    try:
        response = requests.post(
            MULTIMODAL_API_ENDPOINT,
            json={"image_uri": image_uri, "caption": desc},
            headers={"Content-Type": "application/json"},
            timeout=100,
        )

        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()["multimodal_embeds"]

    except requests.exceptions.HTTPError as e:
        logger.exception("Error fetching multimodal embedding: %s", e)
        raise

    except requests.exceptions.RequestException as e:
        logger.exception("Error fetching multimodal embedding: %s", e)
        raise requests.exceptions.HTTPError(
            "Error fetching multimodal embedding", response=requests.Response()
        ) from e

    except (ValueError, TypeError) as e:
        logger.exception(
            "Not able to decode received json from multimodal embedding API: %s", e
        )
        raise requests.exceptions.HTTPError(
            "Invalid response from multimodal embedding API",
            response=requests.Response(),
        ) from e


def get_text_embeddings(text):
    """
    Fetches text embeddings from a text embedding API.

    Args:
        text: The input text.

    Returns:
        The text embeddings as a JSON object.

    Raises:
        requests.exceptions.HTTPError: If there is an error fetching the text embeddings
                                       or the API returns an invalid response.
    """
    try:
        response = requests.post(
            TEXT_API_ENDPOINT,
            json={"caption": text},
            headers={"Content-Type": "application/json"},
            timeout=100,
        )

        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        return response.json()["text_embeds"]

    except requests.exceptions.HTTPError as e:
        logger.exception("Error fetching text embedding: %s", e)
        raise

    except requests.exceptions.RequestException as e:
        logger.exception("Error fetching text embedding: %s", e)
        raise requests.exceptions.HTTPError(
            "Error fetching text embedding", response=requests.Response()
        ) from e

    except (ValueError, TypeError) as e:
        logger.exception(
            "Not able to decode received json from text embedding API: %s", e
        )
        raise requests.exceptions.HTTPError(
            "Invalid response from text embedding API", response=requests.Response()
        ) from e


def get_embeddings(image_uri=None, text=None):
    """
    Fetches embeddings based on the provided input.

    This function can generate text embeddings, image embeddings, or multimodal embeddings
    depending on the input provided.

    Args:
        text: The input text for text embeddings. Defaults to None.
        image_uri: The URI of the image for image embeddings. Defaults to None.

    Returns:
        The embeddings as a JSON object, or None if no valid input is provided.

    Raises:
        requests.exceptions.HTTPError: If there is an error fetching the embeddings from the API.
    """
    if image_uri and text:
        logger.info("Generating MULTIMODAL embeddings...")
        return get_multimodal_embeddings(image_uri, text)
    elif text:
        logger.info("Generating TEXT embeddings...")
        return get_text_embeddings(text)
    elif image_uri:
        logger.info("Generating IMAGE embeddings...")
        return get_image_embeddings(image_uri)
    else:
        logger.error(
            "Missing input. Provide a textual product description and/or image_uri to generate embeddings"
        )
        return None
