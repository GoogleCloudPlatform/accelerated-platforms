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
import alloydb_connect
import json
import logging
import logging.config
import os
from sqlalchemy import text
from google.cloud.alloydb.connector import Connector

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
    catalog_table,
    embedding_column,
    row_count,
    user_query=None,
    image_uri=None,
):
    try:
        embeddings = json.dumps(
            get_emb.get_embeddings(text=user_query, image_uri=image_uri)
        )
        print(embeddings)
        logging.info(embeddings)

        # TODO - do we need separate calls to embeddings methods ?
        # # Get text embedding for user query
        # text_emb = json.dumps(get_emb.get_embeddings(text=user_query))
        # print(text_emb)
        # logging.info(text_emb)

        # # Get image embedding if image uri (gs://)
        # image_emb = json.dumps(get_emb.get_embeddings(image_uri=image_uri))
        # print(image_emb)
        # logging.info(image_emb)

        # # Get text & image were given call multimodal embedding
        # multimodal_emb = json.dumps(get_emb.get_embeddings(text=user_query,image_uri=image_uri))
        # print(multimodal_emb)
        # logging.info(multimodal_emb)

        # Parameterized query
        search_query = f"""SELECT "Name", "Description", "c1_name" as Category, "Specifications", (1-({embedding_column} <-> :emb)) AS cosine_similarity FROM {catalog_table} ORDER BY cosine_similarity DESC LIMIT {row_count};"""
        logging.info(search_query)

        # Execute the query with the embedding as a parameter
        with engine.connect() as conn:
            # Perform a cosine similarity search
            result = conn.execute(
                text(search_query),
                {"emb": embeddings},
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
