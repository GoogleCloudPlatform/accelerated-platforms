from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

# Load the SentenceTransformer model
model = SentenceTransformer("bert-base-nli-stsb-mean-tokens")


@app.route("/get-text-embeddings", methods=["POST"])
def gen_emb():
    try:
        data = request.get_json()
        text = data.get("product_desc")  # TODO: Rename this to user_query

        if not text:
            return jsonify({"error": "No text provided"}), 400

        embeddings = model.encode(text)
        embeddings = [embedding.tolist() for embedding in embeddings]

        return jsonify({"embeddings": embeddings})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
