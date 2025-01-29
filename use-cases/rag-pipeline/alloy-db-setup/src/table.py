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

import asyncio
import logging
import logging.config
import os

import aiohttp
import alloydb_connect
import get_emb
import pandas as pd
import sqlalchemy
from google.cloud.alloydb.connector import Connector
from pgvector.sqlalchemy import Vector

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION"))

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
    )
    logger.setLevel(new_log_level)


async def create_and_populate(
    database: str,
    table_name: str,
    processed_data_path: str,
    max_workers_value: int,
):
    """Creates and populates table, generating embeddings concurrently."""
    try:
        # 1. Extract Data
        df = pd.read_csv(processed_data_path)
        logger.info("Input df shape: %s", df.shape)

        # Drop the products with image_uri as NaN
        df.dropna(subset=["image_uri"], inplace=True)
        logger.info("Resulting df shape: %s", df.shape)

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

        logger.info("Embedding generation completed")

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
                    "Table '%s' created and populated in '%s'.",
                    table_name,
                    database,
                )
    except FileNotFoundError:
        logger.exception("CSV file not found")
    except pd.errors.EmptyDataError:
        logger.exception("Empty CSV file")
    except Exception:
        logger.exception("An unhandled exception occurred")
        raise


def create_embeddings_index(
    database: str,
    table_name: str,
    embedding_column: str,
    index_name: str,
    distance_function: str,
    num_leaves: int,
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
                    "Index '%s' created on '%s', '%s'",
                    index_name,
                    table_name,
                    embedding_column,
                )

    except Exception:
        logger.exception("An unhandled exception occurred during index creation")
        raise
