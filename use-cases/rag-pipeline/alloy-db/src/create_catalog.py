from sqlalchemy import create_engine
import pg8000
import sqlalchemy
from sqlalchemy import text
from google.cloud.alloydb.connector import Connector
import psycopg2

# from sqlalchemy_utils import create_database, database_exists
from pgvector.sqlalchemy import Vector


import pandas as pd
import os
import logging

import google.auth
import google.auth.transport.requests
from google.auth.transport.requests import Request
from google.auth import impersonated_credentials  # Import from the correct module

from get_emb import *

EMBEDDING_DIMESNION = 768

logging.basicConfig(level=logging.INFO)


def create_alloydb_engine(instance_connection_name, db_name, user, password):
    """
    Initializes a SQLAlchemy engine for connecting to AlloyDB.
    """
    connector = Connector()

    def getconn() -> sqlalchemy.engine.Connection:
        conn: sqlalchemy.engine.Connection = connector.connect(
            instance_connection_name,
            "pg8000",
            user=user,  # Optional if using IAM
            password=password,  # Optional if using IAM
            db=db_name,
        )
        return conn

    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine


# NOT WORKING
def get_impersonated_access_token(target_service_account):
    """Obtains an access token by impersonating the target service account."""
    credentials, _ = google.auth.default()

    if isinstance(credentials, google.auth.impersonated_credentials.Credentials):
        # Already impersonating, just refresh
        credentials.refresh(Request())
    else:
        # Impersonate the target service account
        credentials = credentials.with_subject(target_service_account)
        credentials.refresh(Request())

    return credentials.token


# Get the access token
# target_sa = "alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com"
# access_token = get_impersonated_access_token(target_sa)


# This is not working:
# ERROR:root:An error occurred while creating the database: (pg8000.exceptions.DatabaseError)
def create_database_old(instance_uri, database, new_database_name, user, password):
    """Creates a new database in AlloyDB and enables necessary extensions."""
    try:
        # 1. Connect to the default database (e.g., 'postgres')
        engine = create_alloydb_engine(instance_uri, database, user, password)

        # 2. Create the new database
        with engine.connect() as conn:
            conn.execute(text("COMMIT"))  # Commit any potential open transaction
            conn.execute(text(f"CREATE DATABASE {new_database_name}"))
            logging.info(f"Database '{new_database_name}' created successfully.")

        # 3. Connect to the newly created database
        engine = create_alloydb_engine(instance_uri, new_database_name, user, password)

        # 4. Enable extensions in the new database
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logging.info("pgvector extension enabled successfully")

            conn.execute(text("CREATE EXTENSION IF NOT EXISTS alloydb_scann;"))
            logging.info("alloydb_scann extension enabled successfully")

    except Exception as e:
        logging.error(f"An error occurred while creating the database: {e}")

    finally:
        if conn:
            conn.close()


def create_database(host, database, new_database_name, user, access_token):
    """Creates a new database in PostgreSQL using psycopg2."""

    try:
        """
        # Get the access token
        credentials, project = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        logging.info(f"Access Token: {credentials.token}")
        access_token = credentials.token

        """
        # Connect to an existing database (e.g., 'postgres')
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=access_token,
            # use enable_iam_auth to enable IAM authentication
            # enable_iam_auth=True,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE {new_database_name}")
        logging.info(f"Database '{new_database_name}' created successfully.")

        # Connect to the newly created database
        new_db_conn = psycopg2.connect(
            host=host,
            database=new_database_name,
            user=user,
            password=access_token,
            # use enable_iam_auth to enable IAM authentication
            # enable_iam_auth=True,
        )
        new_db_conn.autocommit = True
        new_db_cursor = new_db_conn.cursor()
        # To work with vector embeddings, you must enable the pgvector extension.
        cmd = "CREATE EXTENSION IF NOT EXISTS vector;"
        new_db_cursor.execute(cmd)
        logging.info("pgvector extension enabled successfully")

        # To generate ScaNN indexes, install the alloydb_scann extension in addition to the vector extension.
        cmd = "CREATE EXTENSION IF NOT EXISTS alloydb_scann;"
        new_db_cursor.execute(cmd)
        logging.info("alloydb_scann extension enabled successfully")

    except psycopg2.Error as e:
        logging.error(f"PostgreSQL error: {e}")
        # Handle specific PostgreSQL errors
        # Add more specific error handling here

    except Exception as e:
        logging.error(f"An unexpected error occurred while creating the database: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        if new_db_cursor:
            new_db_cursor.close()
        if new_db_conn:
            new_db_conn.close()


def create_and_populate_table(
    instance_uri, database, user, password, table_name, processed_data_path
):
    """Creates and populates a table in PostgreSQL using pandas and sqlalchemy."""

    try:
        # 1. Extract
        df = pd.read_csv(processed_data_path)
        logging.info(f"Input df shape: {df.shape}")

        # To address: Error communicating with Deployment: Out of range float values are not JSON compliant: nan
        # df = df.fillna("")
        df.dropna(subset=["image_uri"], inplace=True)
        logging.info(f"resulting df shape: {df.shape}")

        # testing with small df
        # df = df[:20]

        # This is temporary. Need a csv file with right gcs image uri
        df["image_uri"] = df["image_uri"].str.replace(
            "gkebatchexpce3c8dcb-rueth-gpu-data/flipkart_images",
            "gkebatchexpce3c8dcb-rueth-gpu-data-bkp/flipkart_images",
        )

        # 2. Transform

        df["multimodal_embeddings"] = df.apply(
            lambda row: get_embeddings(row["Description"], row["image_uri"]), axis=1
        )

        df["text_embeddings"] = df.apply(
            lambda row: get_embeddings(row["Description"], None), axis=1
        )
        df["image_embeddings"] = df.apply(
            lambda row: get_embeddings(None, row["image_uri"]), axis=1
        )
        # 3. Load
        engine = create_alloydb_engine(instance_uri, database, user, password)
        df.to_sql(
            table_name,
            engine,
            if_exists="replace",
            index=False,
            method="multi",
            dtype={
                "multimodal_embeddings": Vector(EMBEDDING_DIMESNION),
                "text_embeddings": Vector(EMBEDDING_DIMESNION),
                "image_embeddings": Vector(EMBEDDING_DIMESNION),
            },
        )
        # df.to_sql(table_name, engine, if_exists="replace", index=False, method="multi")
        logging.info(f"Table '{table_name}' created and populated successfully.")

    except psycopg2.Error as e:
        logging.error(f"PostgreSQL error: {e}")
        # Handle specific PostgreSQL errors
        # Add more specific error handling here

    except FileNotFoundError:
        logging.error(f"Error: CSV file not found at {processed_data_path}")

    except pd.errors.EmptyDataError:
        logging.error("Error: Input CSV file is empty.")

    except Exception as e:
        logging.error(
            f"An unexpected error occurred while creating and populating the table: {e}"
        )


# Create an IVFFlat index on the table with embedding column and cosine distance
def create_text_embeddings_index(
    sql_engine,
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
        with sql_engine.connect() as conn:
            conn.execute(index_cmd)
    except Exception as e:
        # TODO: handle 'postgresql error: access method "scann" does not exist'
        logging.error(f"Error creating index: {e}")
        raise
    else:
        logging.info(f"Index '{INDEX_NAME}' created successfully.")
