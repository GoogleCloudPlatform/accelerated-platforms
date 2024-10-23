#!/usr/bin/env python

import os

from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer
from waitress import serve

app = Flask(__name__)


@app.route("/embed", methods=["POST"])
def encode():
    data = request.json
    sentences = data.get("inputs", [])
    # batch_size = int(os.environ.get("batch_size", 8))
    embeddings = model.encode(sentences)
    # embeddings = encoder.encode(sentences, batch_size=batch_size)
    embeddings = [x.tolist() for x in embeddings]

    return jsonify(embeddings)


if __name__ == "__main__":
    model_name_or_path = os.environ.get("model_name", "bert-base-nli-stsb-mean-tokens")
    print(model_name_or_path)
    model = SentenceTransformer(
        model_name_or_path=model_name_or_path,
        trust_remote_code=True,
    )
    # encoder = SentenceTransformer(model_name_or_path=model_name_or_path)

    serve(app, host="0.0.0.0", port=5000)
