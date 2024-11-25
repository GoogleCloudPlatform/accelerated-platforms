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

import get_emb
import json
import logging
import logging.config
import os
from sqlalchemy import text

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


# TODO: only text input from UI is handled. Need to add image uri to get embeddings
def find_matching_products(
    engine,
    user_query,
    catalog_table,
    embedding_column,
    row_count,
):
    try:
        # Get text embedding for user query
        user_query_emb = json.dumps(get_emb.get_text_embeddings(user_query))
        # logging.info(user_query_emb)

        # TODO: Add a function call to get image embedding if image uri (gs://)
        # image_emb = json.dumps(get_image_embeddings(image_uri))

        # TODO: if both text & image were given call multimodal embedding
        # image_emb = json.dumps(get_multimodal_embeddings(image, text))

        # Parameterized query
        search_query = f"""SELECT "Name", "Description", "c1_name" as Category, "Specifications", (1-({embedding_column} <-> :emb)) AS cosine_similarity FROM {catalog_table} ORDER BY cosine_similarity DESC LIMIT {row_count};"""
        logging.info(search_query)

        # Execute the query with the embedding as a parameter
        with engine.connect() as conn:
            # Perform a cosine similarity search
            result = conn.execute(
                text(search_query),
                {"emb": user_query_emb},
            )

            # logging.info(result)
            response = [row._asdict() for row in result]
            logging.info(response)
            # String format the retrieved information
            retrieved_information = "\n".join(
                [
                    f"{index+1}. "
                    + "\n".join([f"{key}: {value}" for key, value in element.items()])
                    for index, element in enumerate(response)
                ]
            )
        logging.info(retrieved_information)
        return retrieved_information

    except Exception as e:
        logging.error(f"An error occurred while finding matching products: {e}")
    finally:
        if conn:
            conn.close()
