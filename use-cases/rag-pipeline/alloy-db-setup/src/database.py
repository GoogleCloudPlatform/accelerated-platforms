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

import logging
import logging.config
import os

import alloydb_connect
import sqlalchemy
from google.cloud.alloydb.connector import Connector

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
    )
    logger.setLevel(new_log_level)


def create(
    new_database_name: str,
    initial_database_name: str = "postgres",
):
    """Create a new database."""
    try:
        with Connector() as connector:
            pool = alloydb_connect.init_connection_pool(
                connector,
                initial_database_name,
            )
            with pool.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as connection:
                with connection.begin():
                    connection.execute(
                        sqlalchemy.text(f"DROP DATABASE IF EXISTS {new_database_name};")
                    )
                    logger.info(
                        "Database '%s' deleted successfully.", new_database_name
                    )

                    connection.execute(
                        sqlalchemy.text(f"CREATE DATABASE {new_database_name}")
                    )
                    logger.info(
                        "Database '%s' created successfully.", new_database_name
                    )
    except Exception:
        logger.exception("An unhandled exception occurred while creating the database")
        # handle this error?
        # (pg8000.exceptions.DatabaseError) {'S': 'ERROR', 'V': 'ERROR', 'C': '55006', 'M': 'database \"product_catalog\" is being accessed by other users', 'D': 'There are 2 other sessions using the database.', 'F': 'dbcommands.c', 'L': '1788', 'R': 'dropdb'}\n[SQL: DROP DATABASE IF EXISTS product_catalog;]\n(Background on this error at: https://sqlalche.me/e/20/4xp6) """
    finally:
        if connection:
            connection.close()
            logger.info("Database '%s' connection closed", initial_database_name)
        if connector:
            connector.close()
            logger.info("Connector closed")


def enable_extensions(
    database_name: str,
):
    """Enable database extensions."""
    extensions = ["vector", "alloydb_scann"]
    try:
        with Connector() as connector:
            pool = alloydb_connect.init_connection_pool(
                connector,
                database_name,
            )

            logger.info("Connecting to the database")
            with pool.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as db_conn:
                with db_conn.begin():
                    for extension in extensions:
                        db_conn.execute(
                            sqlalchemy.text(
                                f"CREATE EXTENSION IF NOT EXISTS {extension};"
                            )
                        )
                        logger.info(
                            "Extension '%s' enabled successfully on '%s' database",
                            database_name,
                            extension,
                        )
    except Exception:
        logger.exception(
            "An unhandled exception occurred while enabling extensions on the database"
        )
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database '%s' connection closed", database_name)
        if connector:
            connector.close()
            logger.info("Connector closed")


def grant_permissions(
    database_name: str,
    read_users: list[str],
    write_users: list[str],
):
    """Grant permissions on the database."""
    try:
        with Connector() as connector:
            pool = alloydb_connect.init_connection_pool(
                connector,
                database_name,
            )

            with pool.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as db_conn:
                with db_conn.begin():
                    logger.info(
                        "Granting permissions on the '%s' database",
                        database_name,
                    )

                    for read_user in read_users:
                        db_conn.execute(
                            sqlalchemy.text(
                                f'GRANT pg_read_all_data TO "{read_user}";'
                            ),
                        )

                    for write_user in write_users:
                        db_conn.execute(
                            sqlalchemy.text(
                                f'GRANT pg_write_all_data TO "{write_user}";'
                            )
                        )
                        db_conn.execute(
                            sqlalchemy.text(
                                f'GRANT CREATE ON SCHEMA public TO "{write_user}";'
                            )
                        )
    except Exception:
        logger.exception(
            "An unhandled exception occurred while granting permissions on the database"
        )
        raise
