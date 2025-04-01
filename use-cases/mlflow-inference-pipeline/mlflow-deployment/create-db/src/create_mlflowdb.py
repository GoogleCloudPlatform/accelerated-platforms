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

# AlloyDB
instance_uri = os.environ.get("MLP_DB_INSTANCE_URI")

# Use the application default credentials
credentials, project = google.auth.default()
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)
user = credentials.service_account_email.removesuffix(".gserviceaccount.com")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    logger.setLevel(os.environ["LOG_LEVEL"].upper())
    logger.info("Log level set to '%s' via LOG_LEVEL env var", logger.level)


def init_connection_pool(connector: Connector, db: str) -> sqlalchemy.engine.Engine:
    """Initializes a SQLAlchemy engine for connecting to AlloyDB."""

    def getconn():
        logger.info("Connecting to db '%s' as user '%s'", db, user)
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
            logger.error(f"Failed to connect to AlloyDB: {e}")
            raise

    pool = sqlalchemy.create_engine(
        creator=getconn,
        url="postgresql+pg8000://",
        pool_pre_ping=True,
    )
    pool.dialect.description_encoding = None
    logger.info("Connection pool created")
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
                    result = conn.execute(
                        text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}';")
                    ).fetchone()
                    if result:
                        logger.info("Database '%s' creation verified", db_name)
                        return
                    else:
                        raise SQLAlchemyError(f"Database '{db_name}' not found after creation.")
                except SQLAlchemyError as e:
                    logger.warning(
                        f"Verification attempt {attempt} failed: {e}. Retrying in {retry_delay} seconds."
                    )
                    time.sleep(retry_delay)
            raise SQLAlchemyError(f"Failed to verify database '{db_name}' creation after {max_retries} attempts.")

    except SQLAlchemyError as e:
        logger.error(f"Database creation failed: {e}")
        raise  
    except Exception as e:
        logger.exception("An unexpected error occurred during database creation: %s", e)
        raise
    finally:
        connector.close()
        logger.info("Connector closed")


if __name__ == "__main__":
    # default to mlflowdb if not set.
    db_name = os.environ.get("DATABASE_NAME", "mlflowdb")
    try:
        create_database(db_name)
        logger.info(f"Database '{db_name}' creation successful.")
    except SQLAlchemyError as e:
        logger.error(f"Database '{db_name}' creation failed after retries: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during database creation: {e}")