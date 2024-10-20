
import argparse

import base64
import io
import re

from PIL import Image
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud.storage.blob import Blob

from lavis.models import load_model_and_preprocess

import torch

# Load the model and processors, ensuring they're on the correct device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  # Explicitly create a torch.device object
model, vis_processors, txt_processors = load_model_and_preprocess(
    name="blip2_feature_extractor", model_type="pretrain", is_eval=True, device=device # Pass the device object here
)

def get_text_embedding(caption):
    text_input = txt_processors["eval"](caption)
    sample = {"text_input": [text_input]}
    features_text = model.extract_features(sample, mode="text")
    return features_text.text_embeds


def get_image_text_embeddings(image, caption):
    image = vis_processors["eval"](image).unsqueeze(0).to(device)
    text_input = txt_processors["eval"](caption)
    sample = {"image": image, "text_input": [text_input]}

    # Extract multimodal, image, and text features
    features_multimodal = model.extract_features(sample)
    features_image = model.extract_features(sample, mode="image")
    features_text = model.extract_features(sample, mode="text")

    return features_multimodal.multimodal_embeds, features_image.image_embeds, features_text.text_embeds

# Flask app
app = Flask(__name__)

def fetch_image(img_uri):

    storage_client = storage.Client()
    uri = img_uri
    if uri[0:5] == "gs://":
        blob = Blob.from_string(uri, client=storage_client)
        imgf = io.BytesIO()
        blob.download_to_file(imgf, storage_client)
        imgf.seek(0)
    elif uri[0:5] == "data:":
        m = re.match("^data:image/.+;base64,", uri)
        if not m:
            raise ValueError("Invalid data: uri")
        imgf = io.BytesIO(base64.b64decode(uri[m.span()[1]:]))
    else:
        raise NotImplementedError("Only supports gs:// and data: uri")
    img = Image.open(imgf).convert("RGB")
    return img


@app.route("/embeddings", methods=["POST"])
def generate_embeddings():
    if request.method == "POST":
        if request.is_json:
            json_req = request.get_json()
            if "image_uri" not in json_req:
                text_features = get_text_embedding(json_req["caption"])
                return jsonify(
                    {"text_embeds":
                     text_features.tolist()[0][0]})
            image = fetch_image(json_req["image_uri"])
            text = json_req.get("caption", None)
        else:
            if "image" not in request.files:
                return jsonify({"error": "No image provided"}), 400

            image_file = request.files["image"]
            image = Image.open(image_file).convert("RGB")
            text = request.form.get("text")

        if text is None:
            return jsonify({"error": "No text provided"}), 400
    else:
        return jsonify({"error": "Invalid request method"}), 405

    try:
        features_multimodal, features_image, features_text = get_image_text_embeddings(image, text)

        response = {
            "multimodal_embeds": features_multimodal.tolist()[0][0],
            "image_embeds": features_image.tolist()[0][0],
            "text_embeds": features_text.tolist()[0][0],
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
