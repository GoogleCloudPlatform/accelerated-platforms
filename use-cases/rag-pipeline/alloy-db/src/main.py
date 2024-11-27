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

import alloydb_setup
import create_catalog
import logging
import logging.config
import os

# Master_product_catalog.csv
PROCESSED_DATA_BUCKET = os.getenv("PROCESSED_DATA_BUCKET")
MASTER_CATALOG_FILE_NAME = os.getenv("MASTER_CATALOG_FILE_NAME")
processed_data_path = f"gs://{PROCESSED_DATA_BUCKET}/{MASTER_CATALOG_FILE_NAME}"

# Catalog DB
database_name = "postgres"
catalog_db = os.getenv("CATALOG_DB_NAME")
catalog_table = os.getenv("CATALOG_TABLE_NAME")

# Vector Index
EMBEDDING_COLUMN = os.getenv("EMBEDDING_COLUMN")
INDEX_NAME = "rag_text_embeddings_index"
DISTANCE_FUNCTION = "cosine"
NUM_LEAVES_VALUE = int(os.getenv("NUM_LEAVES_VALUE"))

if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")

    logger = logging.getLogger("alloydb")

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

        # Create Index
        create_catalog.create_text_embeddings_index(
            catalog_db,
            catalog_table,
            EMBEDDING_COLUMN,
            INDEX_NAME,
            DISTANCE_FUNCTION,
            NUM_LEAVES_VALUE,
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred during catalog onboarding: {e}")
        raise
