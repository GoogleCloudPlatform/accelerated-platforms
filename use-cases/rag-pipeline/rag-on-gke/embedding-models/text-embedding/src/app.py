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
import os

from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

# from sentence_transformers.util import cos_sim
from waitress import serve

app = Flask(__name__)


@app.route("/embeddings", methods=["POST"])
def encode():
    data = request.json
    embeddings_hashmap = {}
    sentences = data.get("inputs", [])
    embeddings = model.encode(sentences)
    embeddings = [x.tolist() for x in embeddings]
    embeddings_hashmap = {"text_embeddings": embeddings}

    return jsonify(embeddings_hashmap)


if __name__ == "__main__":
    model_name_or_path = os.environ.get("model_name", "bert-base-nli-stsb-mean-tokens")
    print(model_name_or_path)
    model = SentenceTransformer(
        model_name_or_path=model_name_or_path, trust_remote_code=True
    )

    serve(app, host="0.0.0.0", port=5000)
