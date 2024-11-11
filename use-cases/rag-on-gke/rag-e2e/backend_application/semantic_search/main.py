from get_emb import *
import json
import logging
import pg8000
import sqlalchemy
from sqlalchemy import text
from google.cloud.alloydb.connector import Connector
import psycopg2
from pgvector.sqlalchemy import Vector
from sqlalchemy.exc import DatabaseError

logging.basicConfig(level=logging.INFO)

# AlloyDB
project_id = "gkebatchexpce3c8dcb"
region = "us-central1"
cluster_id = "rag-db-karajendran"
instance_id = "primary-instance"
instance_uri = f"projects/{project_id}/locations/{region}/clusters/{cluster_id}/instances/{instance_id}"

# User
username = "catalog-admin"
user_password = "retail"

# Catalog
catalog_db = "product_catalog"
catalog_table = "clothes"

# Vector Index
embedding_column = "text_embeddings"

# To Test
row_count = 5  # No of mathcing products


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


def find_matching_products(engine, user_query):
    try:
        # Get text embedding for user query
        user_query_emb = json.dumps(get_text_embeddings(user_query))
        # logging.info(user_query_emb)

        # Parameterized query
        search_query = f"""SELECT "Id", "Name", "Description", "c1_name" as Category, "Specifications", (1-({embedding_column} <-> :emb)) AS cosine_similarity FROM {catalog_table} ORDER BY cosine_similarity DESC LIMIT {row_count};"""
        logging.info(search_query)

        # Execute the query with the embedding as a parameter
        with engine.connect() as conn:
            # Perform a cosine similarity search
            result = conn.execute(
                text(search_query),
                {"emb": user_query_emb},
            )

            # logging.info(result)
            response = [row._asdict() for row in result]
            logging.info(response)
            # String format the retrieved information
            retrieved_information = "\n".join(
                [
                    f"{index+1}. "
                    + "\n".join([f"{key}: {value}" for key, value in element.items()])
                    for index, element in enumerate(response)
                ]
            )
        logging.info(retrieved_information)
        return retrieved_information

    except Exception as e:
        logging.error(f"An error occurred while finding matching products: {e}")
    finally:
        if conn:
            conn.close()


# TODO: Should be dynamic
if __name__ == "__main__":
    # Get User Query
    user_query1 = "I am looking for cycling shorts for women"
    user_query2 = "I am looking for party wear for girls"
    engine = create_alloydb_engine(
        instance_uri,
        catalog_db,
        username,
        user_password,
    )
    find_matching_products(engine, user_query1)
    find_matching_products(engine, user_query2)
