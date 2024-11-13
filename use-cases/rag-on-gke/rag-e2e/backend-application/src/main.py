from get_emb import *
from semantic_search import *
from rerank import *

from flask import Flask, request, jsonify

import sqlalchemy
from google.cloud.alloydb.connector import Connector

import logging

logging.basicConfig(level=logging.INFO)

# Flask app
app = Flask(__name__)


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


def create_alloydb_engine(instance_uri, db_name, user, password):
    """
    Initializes a SQLAlchemy engine for connecting to AlloyDB.
    """
    connector = Connector()

    def getconn() -> sqlalchemy.engine.Connection:
        conn: sqlalchemy.engine.Connection = connector.connect(
            instance_uri,
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


def prompt_generation(user_query, search_result):
    # Option 1: Emphasize User Intent
    prompt1 = f"""An online shopper is searching for products.  
    Given their query and a list of initial product recommendations, identify ONLY the TOP 3 products that best match the shopper's intent. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 2:  Provide Context and Constraints - works better!
    prompt2 = f"""You are an AI assistant helping an online shopper find the most relevant products.  
    The shopper has submitted a search query, and a preliminary search has returned a list of potential matches. 
    Your task is to refine these results by selecting only the 3 best products from the list without duplicates. 
    Return only the product details in the format as it is in search result. Dont add any additional information
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 3:  Be More Directive
    prompt3 = f"""Rerank the following product recommendations to best satisfy an online shopper's search query. 
    Return only the top 3 most relevant products. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    return prompt2


@app.route("/rag-backend", methods=["POST"])
def backend_e2e():
    try:
        if request.method == "POST":
            if request.is_json:
                json_req = request.get_json()
                logging.info(json_req)
                # TODO: only text input from UI is handled. Need to add image url or file upload
                if "user_query" in json_req:
                    user_query = json_req["user_query"]
                    engine = create_alloydb_engine(
                        instance_uri, catalog_db, username, user_password
                    )
                    product_list = find_matching_products(
                        engine,
                        user_query,  # add image
                        catalog_table,
                        embedding_column,
                        row_count,
                    )
                    logging.info(f"product list returned by db: {product_list}")
                    prompt = prompt_generation(user_query, product_list)
                    logging.info(f"Prompt used to re-rank: {prompt}")
                    reranked_result = query_pretrained_gemma(prompt)
                    logging.info(f"Response to front end: {reranked_result}")
                    return reranked_result
                else:
                    return (
                        jsonify({"error": "No query provided"}),
                        400,
                    )
        else:
            return jsonify({"error": "Invalid request method"}), 405
    except Exception as e:
        logging.error(f"An error occurred while running backend e2e application: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)  # Match the Service port
