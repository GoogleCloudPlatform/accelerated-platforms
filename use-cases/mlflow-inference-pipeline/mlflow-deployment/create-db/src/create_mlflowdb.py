import logging
import logging.config
import os

import google.auth
import google.auth.transport.requests
import sqlalchemy
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
        return connector.connect(db=db, driver="pg8000", enable_iam_auth=True,
                                 instance_uri=instance_uri, ip_type=IPTypes.PSC, user=user)

    pool = sqlalchemy.create_engine(creator=getconn, url="postgresql+pg8000://")
    pool.dialect.description_encoding = None
    logger.info("Connection pool created")
    return pool

def create_database(db_name: str, initial_db: str = "postgres"):
    """Creates a database."""
    connector = Connector()
    try:
        pool = init_connection_pool(connector, initial_db)
        with pool.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(sqlalchemy.text(f"DROP DATABASE IF EXISTS {db_name};"))
            logger.info("Database '%s' dropped (if existed)", db_name)
            conn.execute(sqlalchemy.text(f"CREATE DATABASE {db_name};"))
            logger.info("Database '%s' created", db_name)
    except Exception as e:
        logger.exception("Database creation failed: %s", e)
    finally:
        connector.close()
        logger.info("Connector closed")

if __name__ == "__main__":
    # default to mlflowdb if not set.
    db_name = os.environ.get("DATABASE_NAME", "mlflowdb") 
    create_database(db_name)
    