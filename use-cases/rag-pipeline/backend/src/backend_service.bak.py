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

from typing import Union, Optional
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import semantic_search
import alloydb_connect
import jsonify
import logging
import logging.config
from google.cloud.alloydb.connector import Connector

# catalog_db = os.environ("CATALOG_DB_NAME")
# catalog_table = os.environ("CATALOG_TABLE_NAME")
# embedding_column = os.environ("EMBEDDING_COLUMN")
# env:
#   embedding_column:
#     key1: value1
#     key2: value2
#     key3: value3

catalog_db = "product_catalog"
catalog_table = "clothes"
embedding_column = {
    "text": "text_embeddings",
    "image": "image_embeddings",
    "multimodal": "multimodal_embeddings",
}
row_count = 5  # No of matching products


app = FastAPI()


class TextPrompt(BaseModel):
    text: str


class ImageUriPrompt(BaseModel):
    image_uri: str


class Prompt(BaseModel):
    text: Optional[TextPrompt] = None
    image: Optional[ImageUriPrompt] = None


@app.post("/generate_product_recommendations/")
async def generate_product_recommendations(prompt: Prompt):
    """
    Generates product recommendations based on a text, image, or image+text prompt.
    """

    try:
        with Connector() as connector:
            engine = alloydb_connect.create_alloydb_engine(connector, catalog_db)

        if prompt.text and prompt.image:
            print(prompt.text.text, prompt.image.image_uri)
            # product_list = semantic_search.find_matching_products(
            #     prompt.text.text,
            #     prompt.image.image_uri,
            #     engine,
            #     catalog_table,
            #     embedding_column["text"],
            # )
        elif prompt.text:
            product_list = semantic_search.find_matching_products(
                engine,
                prompt.text.text,
                catalog_table,
                embedding_column["text"],
                row_count,
            )
            logging.info(f"product list returned by db: {product_list}")
            if not product_list:
                return (
                jsonify({"error": "No matching products found"}),
                            404,
             )

        elif prompt.image:
            print(prompt.image)
            #  product_list = semantic_search.find_matching_products(
            #     image_uri=prompt.image.image_uri
            # )

        else:
            raise ValueError("Please provide at least a text or an image prompt.")

    # Format the recommendations
    # formatted_recommendations = ", ".join(recommendations)
    # response = f"These are product recommendations for the given prompt: {formatted_recommendations}"

    return {"response": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
