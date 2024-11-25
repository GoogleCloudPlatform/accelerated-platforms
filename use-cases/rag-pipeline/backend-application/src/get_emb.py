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

service_name = os.getenv(
    "EMBEDDING_MODEL"
)  # matches service name in multimodal-embedding.yaml
namespace = os.getenv("MLP_KUBERNETES_NAMESPACE")
url = f"http://{service_name}.{namespace}.svc.cluster.local:8000/embeddings"
headers = {"Content-Type": "application/json"}


def get_text_embeddings(user_query):

    data = {"product_desc": user_query}
    try:
        response = requests.post(url, headers=headers, json=data)
        # logging.info(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["text_embeds"]
    except requests.exceptions.RequestException as e:

        logging.error(
            f"Error while generating text embedding for text '{user_query}': {e}"
        )
        return None


def get_image_embeddings(image_uri):

    data = {"image_uri": image_uri}
    try:
        response = requests.post(url, headers=headers, json=data)
        # logging.info(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["image_embeds"]
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Error while generating image embedding for image '{image_uri}': {e}"
        )
        return None


def get_multimodal_embeddings(desc, image_uri):

    data = {"product_desc": desc, "image_uri": image_uri}
    try:
        response = requests.post(url, headers=headers, json=data)
        # logging.info(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["multimodal_embeds"]
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Error while generating multimodal embedding for text '{desc}' and image '{image_uri}': {e}"
        )
        return None


def get_embeddings(text=None, image_uri=None):
    if text and image_uri:
        return get_multimodal_embeddings(text, image_uri)
    elif text:
        return get_text_embeddings(text)
    elif image_uri:
        return get_image_embeddings(image_uri)
    else:
        logging.error(
            "Provide product description and/or image_uri to generate embeddings"
        )
        return None
