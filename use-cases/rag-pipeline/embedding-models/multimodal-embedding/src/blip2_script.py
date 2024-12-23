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
import io
import os
import torch

from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud.storage.blob import Blob
from lavis.models import load_model_and_preprocess
from PIL import Image

# Configure logging

logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logger.setLevel(new_log_level)

logger.info("Initializing multimodal model blip2 ...")


# Load the model and processors, ensuring they're on the correct device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model, vis_processors, txt_processors = load_model_and_preprocess(
    name="blip2_feature_extractor", model_type="pretrain", is_eval=True, device=device
)


def get_text_embedding(caption):
    """Generates text embeddings for a given caption.

    Args:
        caption: The input caption as a string.

    Returns:
        A torch.Tensor containing the text embeddings.

    Raises:
        ValueError: If there is an error generating the text embedding.
    """

    try:
        text_input = txt_processors["eval"](caption)
        sample = {"text_input": [text_input]}
        features_text = model.extract_features(sample, mode="text")
        return features_text.text_embeds
    except Exception as e:
        raise ValueError(f"Error generating text embedding: {e}")


def get_image_embedding(image):
    """Generates multimodal embeddings for a given image and caption.

    Args:
        image: A PIL.Image object.
        caption: The input caption as a string.

    Returns:
        A torch.Tensor containing the multimodal embeddings.

    Raises:
        ValueError: If there is an error generating the multimodal embedding.
    """
    try:
        image = vis_processors["eval"](image).unsqueeze(0).to(device)
        sample = {"image": image}
        features_image = model.extract_features(sample, mode="image")
        return features_image.image_embeds
    except Exception as e:
        raise ValueError(f"Error generating image embedding: {e}")


def get_multimodal_embedding(image, caption):
    """Generates multimodal embeddings for a given image and caption.

    Args:
        image: A PIL.Image object.
        caption: The input caption as a string.

    Returns:
        A torch.Tensor containing the multimodal embeddings.

    Raises:
        ValueError: If there is an error generating the multimodal embedding.
    """
    try:
        image = vis_processors["eval"](image).unsqueeze(0).to(device)
        text_input = txt_processors["eval"](caption)
        sample = {"image": image, "text_input": [text_input]}
        features_multimodal = model.extract_features(sample)
        return features_multimodal.multimodal_embeds
    except Exception as e:
        raise ValueError(f"Error generating multimodal embedding: {e}")


# Flask app
app = Flask(__name__)


def download_image_from_gcs(gcs_uri):
    """Downloads an image file from Google Cloud Storage (GCS).

    Args:
        gcs_uri: The GCS URI of the image file (e.g., 'gs://bucket-name/path/to/image.jpg').

    Returns:
        A PIL.Image object.

    Raises:
        ValueError: If the GCS URI is invalid or if there is an error downloading the image.
    """
    try:
        # Validate the GCS URI
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI")

        # Extract bucket name and object name from the URI
        bucket_name, object_name = gcs_uri[5:].split("/", 1)

        # Initialize a GCS client
        storage_client = storage.Client()

        # Get the bucket and blob (object)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        # Download the image into a BytesIO object
        imgf = io.BytesIO()
        blob.download_to_file(imgf)
        imgf.seek(0)

        # Open the image using PIL
        img = Image.open(imgf).convert("RGB")
        return img

    except Exception as e:
        raise ValueError(f"Error downloading image from GCS: {e}")


@app.route("/text_embeddings", methods=["POST"])
def generate_text_embeddings():
    """Generates text embeddings for a given caption.

    This endpoint accepts a POST request with a JSON payload containing the `caption`.

    Args:
        None (from request body):
            caption: The input caption as a string.

    Returns:
        A JSON response containing the text embeddings.
            {
                "text_embeds": [embedding values]
            }

    Raises:
        400 Bad Request: If the request format is invalid or missing required data.
        405 Method Not Allowed: If the request method is not POST.
    """
    if request.method == "POST":
        if request.is_json:
            try:
                json_req = request.get_json()
            except Exception as e:
                return jsonify({"error": f"Invalid JSON payload: {e}"}), 400
            if "caption" not in json_req:
                return jsonify({"error": "No caption provided"}), 400
            try:
                text_features = get_text_embedding(json_req["caption"])
            except Exception as e:
                return jsonify({"error": str(e)}), 400
            logger.info("Text embeddings generated successfully.")
            return jsonify(
                {
                    "text_embeds": text_features.tolist()[0][0],
                }
            )
        else:
            return jsonify({"error": "Invalid request format"}), 400
    else:
        return jsonify({"error": "Invalid request method"}), 405


@app.route("/image_embeddings", methods=["POST"])
def generate_image_embeddings():
    if request.method == "POST":
        try:
            if request.is_json:
                try:
                    json_req = request.get_json()
                except Exception as e:
                    return jsonify({"error": f"Invalid JSON payload: {e}"}), 400
                if "image_uri" not in json_req:
                    return jsonify({"error": "No image_uri provided"}), 400
                try:
                    image = download_image_from_gcs(json_req["image_uri"])
                except Exception as e:
                    return jsonify({"error": str(e)}), 400
            else:
                if "image" not in request.files:
                    return jsonify({"error": "No image provided"}), 400
                try:
                    image_file = request.files["image"]
                    image = Image.open(image_file).convert("RGB")
                except Exception as e:
                    return jsonify({"error": f"Error processing image file: {e}"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

        try:
            image_features = get_image_embedding(image)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        logger.info("Image embeddings generated successfully.")
        return jsonify(
            {
                "image_embeds": image_features.tolist()[0][0],
            }
        )
    else:
        return jsonify({"error": "Invalid request method"}), 405


@app.route("/multimodal_embeddings", methods=["POST"])
def generate_multimodal_embeddings():
    """Generates multimodal embeddings for a given image and caption.

    This endpoint accepts a POST request with either a JSON payload containing
    the `image_uri` and `caption` or a file upload named `image` and a form field
    named `text`.

    Args:
        None (from request body):
            JSON payload:
                image_uri: The GCS URI of the image file.
                caption: The input caption as a string.
            Form data:
                image: The image file.
                text: The input caption as a form field.

    Returns:
        A JSON response containing the multimodal embeddings
    """
    if request.method == "POST":
        try:
            if request.is_json:
                try:
                    json_req = request.get_json()
                except Exception as e:
                    return jsonify({"error": f"Invalid JSON payload: {e}"}), 400
                if "image_uri" not in json_req:
                    return jsonify({"error": "No image_uri provided"}), 400
                if "caption" not in json_req:
                    return jsonify({"error": "No caption provided"}), 400
                try:
                    image = download_image_from_gcs(json_req["image_uri"])
                except Exception as e:
                    return jsonify({"error": str(e)}), 400
                caption = json_req["caption"]
            else:
                if "image" not in request.files:
                    return jsonify({"error": "No image provided"}), 400
                if "text" not in request.form:
                    return jsonify({"error": "No text provided"}), 400
                try:
                    image_file = request.files["image"]
                    image = Image.open(image_file).convert("RGB")
                except Exception as e:
                    return jsonify({"error": f"Error processing image file: {e}"}), 400
                caption = request.form["text"]
        except Exception as e:
            return jsonify({"error": str(e)}), 400

        try:
            multimodal_features = get_multimodal_embedding(image, caption)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        logger.info("Multimodal embeddings generated successfully.")
        return jsonify(
            {
                "multimodal_embeds": multimodal_features.tolist()[0][0],
            }
        )
    else:
        return jsonify({"error": "Invalid request method"}), 405


if __name__ == "__main__":
    logger.info(
        "Multimodal model blip2 is ready to serve embedding generation requests..."
    )
    app.run(host="0.0.0.0", port=os.getenv("PORT", "5000"))
