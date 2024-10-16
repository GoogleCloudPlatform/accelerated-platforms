import torch
from PIL import Image

from lavis.models import load_model_and_preprocess
from flask import Flask, request, jsonify


# Load the model and processors, ensuring they're on the correct device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  # Explicitly create a torch.device object
model, vis_processors, txt_processors = load_model_and_preprocess(
    name="blip2_feature_extractor", model_type="pretrain", is_eval=True, device=device # Pass the device object here
)

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

@app.route("/embeddings", methods=["POST"])
def generate_embeddings():
    if request.method == 'POST':
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image_file = request.files['image']
        text = request.form.get('text')

        if text is None:
            return jsonify({'error': 'No text provided'}), 400

        try:
            image = Image.open(image_file).convert('RGB')

            features_multimodal, features_image, features_text = get_image_text_embeddings(image, text)

            response = {
                # 'multimodal_embeds': features_multimodal.multimodal_embeds.tolist(),
                # 'image_embeds': features_image.image_embeds.tolist(),
                # 'text_embeds': features_text.text_embeds.tolist(),
                'multimodal_embeds': features_multimodal.tolist(),
                'image_embeds': features_image.tolist(),
                'text_embeds': features_text.tolist(),
            }

            return jsonify(response)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    else:
        return jsonify({'error': 'Invalid request method'}), 405


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
