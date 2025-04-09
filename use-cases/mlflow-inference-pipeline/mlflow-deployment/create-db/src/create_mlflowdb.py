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
import time

import google.auth
import google.auth.transport.requests
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from google.cloud.alloydb.connector import Connector, IPTypes
from sqlalchemy.orm import Session  # Import Session for cleaner context management

# AlloyDB
instance_uri = os.environ.get("MLP_DB_INSTANCE_URI")

# Authentication
credentials, project = google.auth.default()
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)
user = credentials.service_account_email.removesuffix(".gserviceaccount.com")

# Logging Configuration
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()  # Default to INFO
try:
    logger.setLevel(log_level_str)
    logger.info(f"Log level set to '{log_level_str}' via LOG_LEVEL env var")
except ValueError:
    logger.warning(
        f"Invalid log level '{log_level_str}' specified in LOG_LEVEL. Using default: INFO."
    )
    logger.setLevel(logging.INFO)


def init_connection_pool(connector: Connector, db: str) -> sqlalchemy.engine.Engine:
    """Initializes a SQLAlchemy engine for connecting to AlloyDB."""

    def getconn():
        logger.info(f"Connecting to database '{db}' as user '{user}'")
        try:
            conn = connector.connect(
                db=db,
                driver="pg8000",
                enable_iam_auth=True,
                instance_uri=instance_uri,
                ip_type=IPTypes.PSC,
                user=user,
            )
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to AlloyDB for database '{db}': {e}")
            raise

    pool = sqlalchemy.create_engine(
        creator=getconn,
        url="postgresql+pg8000://",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )
    pool.dialect.description_encoding = None
    logger.info(f"Connection pool created for database '{db}'")
    return pool


def create_database(db_name: str, initial_db: str = "postgres"):
    """Creates a database with error handling and verification."""
    connector = Connector()
    try:
        pool = init_connection_pool(connector, initial_db)
        with pool.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Drop the database if it exists (for idempotency or testing)
            conn.execute(sqlalchemy.text(f"DROP DATABASE IF EXISTS {db_name};"))
            logger.info("Database '%s' dropped (if existed)", db_name)

            # Create the database
            conn.execute(sqlalchemy.text(f"CREATE DATABASE {db_name};"))
            logger.info("Database '%s' creation initiated", db_name)

            # Verify database creation
            max_retries = 3
            retry_delay = 5
            for attempt in range(1, max_retries + 1):
                try:
                    # Establish a new connection to the newly created database for verification
                    verification_pool = init_connection_pool(connector, db_name)
                    with verification_pool.connect() as verification_conn:
                        result = verification_conn.execute(
                            text(
                                f"SELECT 1 FROM pg_database WHERE datname='{db_name}';"
                            )
                        ).fetchone()
                        if result:
                            logger.info("Database '%s' creation verified", db_name)
                            break
                        else:
                            raise SQLAlchemyError(
                                f"Database '{db_name}' not found after creation."
                            )
                except SQLAlchemyError as e:
                    logger.warning(
                        f"Verification attempt {attempt} failed: {e}. Retrying in {retry_delay} seconds."
                    )
                    time.sleep(retry_delay)
                finally:
                    if verification_pool:
                        verification_pool.dispose()
            else:
                raise SQLAlchemyError(
                    f"Failed to verify database '{db_name}' creation after {max_retries} attempts."
                )

    except SQLAlchemyError as e:
        logger.error(f"Database creation failed: {e}")
        raise
    except Exception as e:
        logger.exception("An unexpected error occurred during database creation: %s", e)
        raise
    finally:
        connector.close()
        logger.info("Connector closed")


def grant_permissions(db_name: str, user_name: str):
    """Grants all privileges on the public schema of the specified database to the given user."""
    connector = Connector()
    pool = None
    try:
        pool = init_connection_pool(connector, db_name)
        with Session(pool) as session:
            logger.info(
                f"Granting ALL privileges on schema 'public' of database '{db_name}' to user '{user_name}'"
            )
            # Add double quotes around the username
            quoted_user_name = f'"{user_name}"'
            # Grant ALL privileges on the public schema to the user
            session.execute(text(f"GRANT ALL ON SCHEMA public TO {quoted_user_name};"))
            session.commit()
            logger.info(
                f"Successfully granted ALL privileges on schema 'public' of database '{db_name}' to user '{user_name}'"
            )
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to grant permissions to user '{user_name}' on database '{db_name}': {e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while granting permissions to user '{user_name}' on database '{db_name}': {e}"
        )
        raise
    finally:
        if connector:
            connector.close()
            logger.info("Connector closed")
        if pool:
            pool.dispose()


if __name__ == "__main__":
    db_name = os.environ.get("MLFLOW_DATABASE_NAME", "mlflowdb")
    user_name = os.environ.get("MLP_DB_USER_IAM")

    try:
        create_database(db_name)
        logger.info(f"Database '{db_name}' creation successful.")
    except SQLAlchemyError as e:
        logger.error(f"Database '{db_name}' creation failed after retries: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during database creation: {e}")

    try:
        grant_permissions(db_name, user_name)
        logger.info(
            f"Permissions granted to user '{user_name}' on database '{db_name}'."
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to grant permissions to user '{user_name}' on database '{db_name}': {e}"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred while granting permissions: {e}")
