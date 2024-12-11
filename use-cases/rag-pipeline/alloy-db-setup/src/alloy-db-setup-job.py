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


import create_catalog
import logging
import logging.config
import os

# Master_product_catalog.csv
PROCESSED_DATA_BUCKET = os.environ.get("PROCESSED_DATA_BUCKET")
MASTER_CATALOG_FILE_NAME = os.environ.get("MASTER_CATALOG_FILE_NAME")
processed_data_path = f"gs://{PROCESSED_DATA_BUCKET}/{MASTER_CATALOG_FILE_NAME}"

# Catalog DB
database_name = "postgres"
catalog_db = os.environ.get("CATALOG_DB")
catalog_table = os.environ.get("CATALOG_TABLE_NAME")

# Vector Index
# EMBEDDING_COLUMN = os.environ.get("EMBEDDING_COLUMN")
# INDEX_NAME_TEXT = "rag_text_embeddings_index"
DISTANCE_FUNCTION = "cosine"
NUM_LEAVES_VALUE = int(os.environ.get("NUM_LEAVES_VALUE"))

embedding_columns = {
    "text": "text_embeddings",
    "image": "image_embeddings",
    "multimodal": "multimodal_embeddings",
}

index_names = {
    "text": "rag_text_embeddings_index",
    "image": "rag_image_embeddings_index",
    "multimodal": "rag_multimodal_embeddings_index",
}

if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")

    logger = logging.getLogger("alloydb-catalog-onboarding")

    if "LOG_LEVEL" in os.environ:
        new_log_level = os.environ["LOG_LEVEL"].upper()
        logger.info(
            f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
        )
        logging.getLogger().setLevel(new_log_level)
        logger.setLevel(new_log_level)

    try:

        # Create Database - This function enables the vector, scann extensions as well
        create_catalog.create_database(
            database_name,
            catalog_db,
        )

        # ETL
        create_catalog.create_and_populate_table(
            catalog_db,
            catalog_table,
            processed_data_path,
        )
        # Create Indexes for all embedding columns(text, image and multimodal)
        # <TODO> Validate if image and multimodal scan index is required
        for modality, embedding_column in embedding_columns.items():
            index_name = index_names[modality]

            create_catalog.create_embeddings_index(
                catalog_db,
                catalog_table,
                embedding_column,
                index_name,
                DISTANCE_FUNCTION,
                NUM_LEAVES_VALUE,
            )
    except Exception as e:
        logging.error(f"An unexpected error occurred during catalog onboarding: {e}")
        raise
