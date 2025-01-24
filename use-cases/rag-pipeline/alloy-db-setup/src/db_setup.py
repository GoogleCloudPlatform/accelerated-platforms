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

import argparse
import asyncio
import logging
import logging.config
import os

import database
import table

# Environment variables

# Master_product_catalog.csv
PROCESSED_DATA_BUCKET = os.environ.get("PROCESSED_DATA_BUCKET")
MASTER_CATALOG_FILE_NAME = os.environ.get("MASTER_CATALOG_FILE_NAME")
processed_data_path = f"gs://{PROCESSED_DATA_BUCKET}/{MASTER_CATALOG_FILE_NAME}"

# Catalog DB
catalog_db_name = os.environ.get("CATALOG_DB")
catalog_table_name = os.environ.get("CATALOG_TABLE_NAME")

db_read_users = [
    user.strip() for user in os.environ.get("DB_READ_USERS", default="").split(",")
]
db_write_users = [
    user.strip() for user in os.environ.get("DB_WRITE_USERS", default="").split(",")
]

DISTANCE_FUNCTION = "cosine"
NUM_LEAVES_VALUE = int(os.environ.get("NUM_LEAVES_VALUE"))
# max_workers_value = int(os.environ.get("MAX_WORKERS_VALUE"))
max_workers_value = 32

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


# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
    )
    logger.setLevel(new_log_level)


def initialize_database():
    """Initialize the database"""
    try:
        logger.info("Creating the database...")
        database.create(
            new_database_name=catalog_db_name,
        )
        logger.info("Database created successfully")

        logger.info("Enabling extensions...")
        database.enable_extensions(
            database_name=catalog_db_name,
        )
        logger.info("Extensions enabled successfully")

        logger.info("Granting permissions...")
        database.grant_permissions(
            database_name=catalog_db_name,
            read_users=db_read_users,
            write_users=db_write_users,
        )
        logger.info("Permissions granted successfully")
    except Exception:
        logger.exception(
            "An unhandled exception occurred during database initialization"
        )
        raise


def populate_table():
    """Populate the table"""
    try:
        # ETL Run
        logger.info("Generate embeddings...")
        asyncio.run(
            table.create_and_populate(
                database=catalog_db_name,
                max_workers_value=max_workers_value,
                processed_data_path=processed_data_path,
                table_name=catalog_table_name,
            )
        )
        logger.info("Embeddings generated successfully")

        # Create Indexes for all embedding columns(text, image and multimodal)
        logger.info("Create SCaNN indexes...")
        for modality, embedding_column in embedding_columns.items():
            index_name = index_names[modality]

            table.create_embeddings_index(
                database=catalog_db_name,
                distance_function=DISTANCE_FUNCTION,
                embedding_column=embedding_column,
                index_name=index_name,
                num_leaves=NUM_LEAVES_VALUE,
                table_name=catalog_table_name,
            )
        logger.info("SCaNN indexes have been created successfully")
    except Exception:
        logger.exception("An unhandled exception occurred while populating the table")
        raise


if __name__ == "__main__":
    logger = logging.getLogger("db_setup")

    parser = argparse.ArgumentParser(description="Optional app description")
    parser.add_argument("--initialize-database", action="store_true")
    parser.add_argument("--populate-table", action="store_true")

    args = parser.parse_args()

    if args.initialize_database:
        initialize_database()

    if args.populate_table:
        populate_table()
