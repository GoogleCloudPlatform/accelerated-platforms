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

import alloydb_connect
import get_emb
import logging
import logging.config
import os
import pandas as pd
import sqlalchemy

from google.cloud.alloydb.connector import Connector
from pgvector.sqlalchemy import Vector

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    try:
        # Convert the string to a logging level constant
        numeric_level = getattr(logging, new_log_level)

        # Set the level for the root logger
        logging.setLevel(numeric_level)

        logger.info(
            "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
        )

    except AttributeError:
        logger.warning(
            "Invalid LOG_LEVEL value: '%s'. Using default log level.", new_log_level
        )


EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION"))

def create_database(database, new_database):
    """Creates a new database in AlloyDB and enables necessary extensions."""
    try:
        # 1. Connect to the default database (e.g., 'postgres')
        # initialize Connector as context manager
        with Connector() as connector:
            # initialize connection pool
            pool = alloydb_connect.init_connection_pool(connector, database)
            del_db = sqlalchemy.text(f"DROP DATABASE IF EXISTS {new_database};")
            create_db = sqlalchemy.text(f"CREATE DATABASE {new_database}")

            # interact with AlloyDB database using connection pool
            with pool.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as connection:
                with connection.begin():
                    connection.execute(del_db)
                    logging.info(f"Database '{new_database}' deleted successfully.")
                    connection.execute(create_db)
                    logging.info(f"Database '{new_database}' created successfully.")
    except Exception as e:
        logging.error(f"An error occurred while creating the database: {e}")
        # handle this error?
        # (pg8000.exceptions.DatabaseError) {'S': 'ERROR', 'V': 'ERROR', 'C': '55006', 'M': 'database \"product_catalog\" is being accessed by other users', 'D': 'There are 2 other sessions using the database.', 'F': 'dbcommands.c', 'L': '1788', 'R': 'dropdb'}\n[SQL: DROP DATABASE IF EXISTS product_catalog;]\n(Background on this error at: https://sqlalche.me/e/20/4xp6) """
    finally:
        if connection:
            connection.close()
            logging.info(f"DB: {database} Connection closed")
        if connector:
            connector.close()
            logging.info("Connector closed")
    try:
        # 3. Connect to the newly created database
        with Connector() as connector:
            # initialize connection pool
            pool = alloydb_connect.init_connection_pool(connector, new_database)
            create_vector_extn = sqlalchemy.text(
                f"CREATE EXTENSION IF NOT EXISTS vector;"
            )
            # interact with AlloyDB database using connection pool
            with pool.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as db_conn:
                with db_conn.begin():
                    logging.info(f"Connected with the newly created db {new_database}")
                    # 4. Enable extensions in the new database
                    db_conn.execute(create_vector_extn)
                    logging.info(
                        f"pgvector extension enabled successfully on db {new_database}."
                    )
                    create_scann_extn = sqlalchemy.text(
                        f"CREATE EXTENSION IF NOT EXISTS alloydb_scann;"
                    )
                    db_conn.execute(create_scann_extn)
                    logging.info(
                        f"alloydb_scann extension enabled successfully on db {new_database}."
                    )
    except Exception as e:
        logging.error(f"An error occurred while enabling the extensions: {e}")
    finally:
        if db_conn:
            db_conn.close()
            logging.info(f"DB: {new_database} Connection closed")
        if connector:
            connector.close()
            logging.info("Connector closed")


def create_and_populate_table(database, table_name, processed_data_path):
    """Creates and populates a table in PostgreSQL using pandas and sqlalchemy."""

    try:
        # 1. Extract
        df = pd.read_csv(processed_data_path)
        logging.info(f"Input df shape: {df.shape}")

        # Dropping products with image_uri as NaN
        df.dropna(subset=["image_uri"], inplace=True)
        logging.info(f"resulting df shape: {df.shape}")

        logging.info(f"Starting embedding generation...")
        # 2. Transform
        logging.info(f"Starting multimodal embedding generation...")
        df["multimodal_embeddings"] = df.apply(
            lambda row: get_emb.get_embeddings(row["image_uri"], row["Description"]),
            axis=1,
        )
        logging.info(f"Multimodal embedding generation completed")

        logging.info(f"Starting text embedding generation...")
        df["text_embeddings"] = df.apply(
            lambda row: get_emb.get_embeddings(None, row["Description"]), axis=1
        )
        logging.info(f"Text embedding generation completed")

        logging.info(f"Starting image embedding generation...")
        df["image_embeddings"] = df.apply(
            lambda row: get_emb.get_embeddings(row["image_uri"], None), axis=1
        )
        logging.info(f"Image embedding generation completed")

        logging.info(f"Embedding generation task is now complete")

        # 3. Load
        with Connector() as connector:
            engine = alloydb_connect.init_connection_pool(connector, database)
            with engine.begin() as connection:
                logging.info(f"Connected with the db {database}")
                df.to_sql(
                    table_name,
                    connection,
                    if_exists="replace",
                    index=False,
                    method="multi",
                    dtype={
                        "multimodal_embeddings": Vector(EMBEDDING_DIMENSION),
                        "text_embeddings": Vector(EMBEDDING_DIMENSION),
                        "image_embeddings": Vector(EMBEDDING_DIMENSION),
                    },
                )
                logging.info(
                    f"Table '{table_name}' created and populated successfully on db {database}."
                )
                connection.commit()

    except FileNotFoundError:
        logging.error(f"Error: CSV file not found at {processed_data_path}")

    except pd.errors.EmptyDataError:
        logging.error("Error: Input CSV file is empty.")

    except Exception as e:
        logging.error(
            f"An unexpected error occurred while creating and populating the table: {e}"
        )
    finally:
        if connection:
            connection.close()
            logging.info(f"DB: {database} Connection closed")
        if connector:
            connector.close()
            logging.info("Connector closed")


# Create an Scann index on the table with embedding column and cosine distance
def create_embeddings_index(
    database,
    TABLE_NAME,
    EMBEDDING_COLUMN,
    INDEX_NAME,
    DISTANCE_FUNCTION,
    NUM_LEAVES_VALUE,
):
    index_cmd = sqlalchemy.text(
        f"CREATE INDEX {INDEX_NAME} ON {TABLE_NAME} USING scann ({EMBEDDING_COLUMN} {DISTANCE_FUNCTION}) WITH (num_leaves={NUM_LEAVES_VALUE});"
    )
    try:
        with Connector() as connector:
            pool = alloydb_connect.init_connection_pool(connector, database)
            with pool.connect() as db_conn:
                db_conn.execute(index_cmd)
                logging.info(
                    f"Embedding Column '{EMBEDDING_COLUMN}' : SCaNN Index '{INDEX_NAME}' created successfully."
                )
    except Exception as e:
        # TODO: handle 'postgresql error: access method "scann" does not exist'
        # TODO: Handle "Error creating index: (pg8000.exceptions.DatabaseError) {'S': 'ERROR', 'V': 'ERROR', 'C': 'XX000', 'M': 'Cannot create ScaNN index, error: FAILED_PRECONDITION: Cannot create ScaNN index with empty table. Once the table is populated with data, create the index.
        logging.error(f"Error creating index: {e}")
        raise
    finally:
        if db_conn:
            db_conn.close()
            logging.info(f"DB: {database} Connection closed")
        if connector:
            connector.close()
            logging.info("Connector closed")
