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

import json
import logging
import logging.config
import os

import generate_embeddings
import pandas as pd
from google.cloud.alloydb.connector import Connector
from sqlalchemy import text

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logger.setLevel(new_log_level)


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
            generate_embeddings.get_embeddings(text=user_query, image_uri=image_uri)
        )
        logger.info(
            "Generated embeddings for %s text and %s image_uri %s embeddings",
            user_query,
            image_uri,
            embeddings,
        )

        # Parameterized query
        search_query = f"""SELECT "Name", "Description", "c1_name" as Category, "Specifications", "Id" as Product_Id, "Brand" , "image_uri" , (1-({embedding_column} <-> :emb)) AS cosine_similarity FROM {catalog_table} ORDER BY cosine_similarity DESC LIMIT {row_count};"""
        logger.info(
            "Semantic Search Query to get product recommendations sorted by Cosine distance: %s ",
            search_query,
        )

        # Execute the query with the embedding as a parameter
        with engine.connect() as conn:
            # Perform a cosine similarity search
            result = conn.execute(
                text(search_query),
                {"emb": embeddings},
            )

            df = pd.DataFrame(result.fetchall())
            df.columns = result.keys()  # Set column names

        logger.info("Semantic Search results received from DB %s: ")

        # Print all columns with keys and values
        for index, row in df.iterrows():
            print(f"Row {index + 1}:")
            for key, value in row.items():
                print(f"  {key}: {value}")
            print("-" * 20)  # Add a separator between rows

        # Drop specified columns to remove cosine bias and re-ranking results later in path
        columns_to_drop = [
            "Description",
            "cosine_similarity",
            "Brand",
            "product_id",
            "image_uri",
        ]  # List the columns to drop
        df = df.drop(columns=columns_to_drop)

        logger.info("Semantic Search results received from DB: %s", df)
        # Convert the DataFrame to a string and dropped row Index
        retrieved_information = df.to_string(index=False)

        logger.info(
            "Formatted response for the Semantic Search Query from DB: "
            + retrieved_information
        )
        return retrieved_information

    except Exception as e:
        logger.error(f"An error occurred while finding matching products: {e}")

    finally:
        if conn:
            conn.close()
