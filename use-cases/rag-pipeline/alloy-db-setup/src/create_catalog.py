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
import asyncio
import get_emb
import logging
import logging.config
import os
import pandas as pd
import sqlalchemy

import aiohttp
from google.cloud.alloydb.connector import Connector
from pgvector.sqlalchemy import Vector

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION"))

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logger.setLevel(new_log_level)


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
                    logger.info(f"Database '{new_database}' deleted successfully.")
                    connection.execute(create_db)
                    logger.info(f"Database '{new_database}' created successfully.")
    except Exception as e:
        logger.error(f"An error occurred while creating the database: {e}")
        # handle this error?
        # (pg8000.exceptions.DatabaseError) {'S': 'ERROR', 'V': 'ERROR', 'C': '55006', 'M': 'database \"product_catalog\" is being accessed by other users', 'D': 'There are 2 other sessions using the database.', 'F': 'dbcommands.c', 'L': '1788', 'R': 'dropdb'}\n[SQL: DROP DATABASE IF EXISTS product_catalog;]\n(Background on this error at: https://sqlalche.me/e/20/4xp6) """
    finally:
        if connection:
            connection.close()
            logger.info(f"DB: {database} Connection closed")
        if connector:
            connector.close()
            logger.info("Connector closed")
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
                    logger.info(f"Connected with the newly created db {new_database}")
                    # 4. Enable extensions in the new database
                    db_conn.execute(create_vector_extn)
                    logger.info(
                        f"pgvector extension enabled successfully on db {new_database}."
                    )
                    create_scann_extn = sqlalchemy.text(
                        f"CREATE EXTENSION IF NOT EXISTS alloydb_scann;"
                    )
                    db_conn.execute(create_scann_extn)
                    logger.info(
                        f"alloydb_scann extension enabled successfully on db {new_database}."
                    )
    except Exception as e:
        logger.error(f"An error occurred while enabling the extensions: {e}")
    finally:
        if db_conn:
            db_conn.close()
            logger.info(f"DB: {new_database} Connection closed")
        if connector:
            connector.close()
            logger.info("Connector closed")


async def create_and_populate_table(
    database, table_name, processed_data_path, max_workers_value
):
    """Creates and populates table, generating embeddings concurrently."""
    try:
        # 1. Extract Data
        df = pd.read_csv(processed_data_path)
        logger.info(f"Input df shape: {df.shape}")

        # Drop the products with image_uri as NaN
        df.dropna(subset=["image_uri"], inplace=True)
        logger.info(f"resulting df shape: {df.shape}")

        # 2. Transform: Embedding Generation (aiohttp)
        num_rows = len(df)
        embedding_tasks = []
        logger.info("Starting embedding generation...")

        # ClientSession outside loop for connection reuse. Timeout included.
        timeout_settings = aiohttp.ClientTimeout(
            total=300, sock_connect=10, sock_read=60
        )
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=max_workers_value),
            raise_for_status=True,
            timeout=timeout_settings,
        ) as session:
            for i in range(num_rows):
                row = df.iloc[i]
                # Start all tasks concurrently for max performance
                embedding_tasks.append(
                    get_emb.get_embeddings_async(
                        session,
                        row["image_uri"],
                        row["Description"],
                        timeout_settings,
                    )
                )
                embedding_tasks.append(
                    get_emb.get_embeddings_async(
                        session,
                        text=row["Description"],
                        timeout_settings=timeout_settings,
                    )
                )
                embedding_tasks.append(
                    get_emb.get_embeddings_async(
                        session,
                        image_uri=row["image_uri"],
                        timeout_settings=timeout_settings,
                    )
                )

            all_results = await asyncio.gather(*embedding_tasks)

        # Reshape Results
        multimodal_results = all_results[::3]
        text_results = all_results[1::3]
        image_results = all_results[2::3]

        df["multimodal_embeddings"] = multimodal_results
        df["text_embeddings"] = text_results
        df["image_embeddings"] = image_results

        logger.info("Embedding generation complete...")

        # 3. Load (Synchronous Database Loading)
        with Connector() as connector:
            engine = alloydb_connect.init_connection_pool(connector, database)
            with engine.begin() as conn:  # Use conn for consistency
                df.to_sql(
                    table_name,
                    conn,
                    if_exists="replace",
                    index=False,
                    method="multi",
                    dtype={
                        "multimodal_embeddings": Vector(EMBEDDING_DIMENSION),
                        "text_embeddings": Vector(EMBEDDING_DIMENSION),
                        "image_embeddings": Vector(EMBEDDING_DIMENSION),
                    },
                )
                logger.info(
                    f"Table '{table_name}' created and populated in '{database}'."
                )

    except FileNotFoundError as e:
        logger.exception(f"CSV file not found: {e}")

    except pd.errors.EmptyDataError as e:
        logger.exception(f"Empty CSV file: {e}")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        raise


def create_embeddings_index(
    database, table_name, embedding_column, index_name, distance_function, num_leaves
):
    """Creates a ScaNN index on the specified embedding column."""

    try:
        with Connector() as connector:
            pool = alloydb_connect.init_connection_pool(connector, database)
            with pool.connect() as conn:  # Use conn for consistency
                index_cmd = sqlalchemy.text(
                    f"""CREATE INDEX {index_name} ON {table_name} 
                       USING scann ({embedding_column} {distance_function}) 
                       WITH (num_leaves={num_leaves});"""
                )
                conn.execute(index_cmd)
                logger.info(
                    f"Index '{index_name}' created on '{table_name}'.{embedding_column}"
                )

    except Exception as e:
        logger.exception(f"Error creating index: {e}")
        raise
