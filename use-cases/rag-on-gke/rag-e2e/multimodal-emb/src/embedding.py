import argparse
import base64
import io
import re
import logging

from PIL import Image
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud.storage.blob import Blob

from lavis.models import load_model_and_preprocess

import torch

# Load the model and processors, ensuring they're on the correct device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model, img_processor, text_processor = load_model_and_preprocess(
    name="blip2_feature_extractor", model_type="pretrain", is_eval=True, device=device
)


def fetch_image(img_uri):
    """
    Fetches an image from Google Cloud Storage (GCS) or a data URI.

    Args:
      img_uri: The URI of the image.

    Returns:
      A PIL Image object.
    """
    try:
        storage_client = storage.Client()
        uri = img_uri
        if uri.startswith("gs://"):
            blob = Blob.from_string(uri, client=storage_client)
            imgf = io.BytesIO()
            blob.download_to_file(imgf, storage_client)
            imgf.seek(0)
        else:
            raise NotImplementedError("Only supports GCS URI")
        img = Image.open(imgf).convert("RGB")
        return img
    except Exception as e:
        logging.error(f"Error fetching image from {img_uri}: {e}")
        raise


def get_text_embedding(product_desc: str):
    """
    Generates text embeddings for a given product_desc.

    Args:
      product_desc: The input product description string.

    Returns:
      A tensor containing the text embeddings.
    """
    try:
        text_input = text_processor["eval"](product_desc)
        print(text_input)
        sample = {"text_input": [text_input]}
        features_text = model.extract_features(sample, mode="text")
        print(len(features_text.text_embeds))
        return features_text.text_embeds
    except Exception as e:
        logging.error(f"Error generating text embedding: {e}")
        raise


def get_image_embeddings(image):
    """
    Generates image embeddings for a given image uri

    Args:
      image: image file path (GCS URI)

    Returns:
      A tensor containing the text embeddings.
    """
    try:
        image = img_processor["eval"](image).unsqueeze(0).to(device)
        sample = {"image": image}
        features_image = model.extract_features(sample, mode="image")

        return features_image.image_embeds
    except Exception as e:
        logging.error(f"Error generating image embedding: {e}")
        raise


def get_multimodal_embeddings(image, text):
    try:
        image = img_processor["eval"](image).unsqueeze(0).to(device)
        text_input = text_processor["eval"](text)
        sample = {"image": image, "text_input": [text_input]}

        # Extract multimodal, image, and text features
        features_multimodal = model.extract_features(sample)
        logging.error(features_multimodal.multimodal_embeds)
        return features_multimodal.multimodal_embeds
    except Exception as e:
        logging.error(f"Error generating multimodal embedding: {e}")
        raise


# Flask app
app = Flask(__name__)


@app.route("/embeddings", methods=["POST"])
def generate_embeddings():
    """
    Generates embeddings for a given image and/or caption.

    Returns:
      A JSON response containing the generated embeddings.
    """
    try:
        if request.method == "POST":
            if request.is_json:
                json_req = request.get_json()
                logging.error(json_req)
                if "image_uri" in json_req and "product_desc" in json_req:
                    logging.error("Multi modal embedding request")
                    image = fetch_image(json_req["image_uri"])
                    text = json_req["product_desc"]
                    features_multimodal = get_multimodal_embeddings(image, text)
                    response = {"multimodal_embeds": features_multimodal.tolist()[0][0]}
                    return jsonify(response)
                elif "image_uri" not in json_req and "product_desc" in json_req:
                    logging.error("Text embedding request")
                    image = None
                    text = json_req["product_desc"]
                    text_features = get_text_embedding(text)
                    return jsonify({"text_embeds": text_features.tolist()[0][0]})
                elif "image_uri" in json_req and "product_desc" not in json_req:
                    logging.error("Image embedding request")
                    image = fetch_image(json_req["image_uri"])
                    text = None
                    image_features = get_image_embeddings(image)
                    return jsonify({"image_embeds": image_features.tolist()[0][0]})
                else:
                    if "image" not in request.files:
                        return (
                            jsonify(
                                {"error": "No image, No product description provided"}
                            ),
                            400,
                        )

                # image_file = request.files["image"]
                # image = Image.open(image_file).convert("RGB")
                # text = request.form.get("text")
        else:
            return jsonify({"error": "Invalid request method"}), 405

    except Exception as e:
        logging.error(f"Error generating embeddings: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)  # Match the Service port
