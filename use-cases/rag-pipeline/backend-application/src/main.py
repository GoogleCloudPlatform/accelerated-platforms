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


import google.auth
import google.auth.transport.requests
import logging
import logging.config
import os
import sqlalchemy

import get_emb
import rerank
import semantic_search

from flask import Flask, request, jsonify
from google.cloud.alloydb.connector import Connector, IPTypes

credentials, project = google.auth.default()
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)

user = credentials.service_account_email.removesuffix(".gserviceaccount.com")
password = credentials.token

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("backend")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)

# Flask app
app = Flask(__name__)

# AlloyDB
instance_uri = os.getenv("MLP_DB_INSTANCE_URI")

# Catalog DB
catalog_db = os.getenv("CATALOG_DB_NAME")
catalog_table = os.getenv("CATALOG_TABLE_NAME")
user = os.getenv("MLP_DB_ADMIN_IAM")

# Vector Index
embedding_column = os.getenv("EMBEDDING_COLUMN")

# To Test
row_count = 5  # No of matching products


def create_alloydb_engine(
    connector: Connector, db="postgres"
) -> sqlalchemy.engine.Engine:
    """
    Initializes a SQLAlchemy engine for connecting to AlloyDB.
    """

    def getconn():
        conn = connector.connect(
            instance_uri,
            "pg8000",
            user=user,
            db=db,
            # use ip_type to specify PSC
            ip_type=IPTypes.PSC,
            # use enable_iam_auth to enable IAM authentication
            enable_iam_auth=True,
        )
        return conn

    # create connection pool
    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    logging.info("Connection pool created successfully.")
    return pool


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
                    with Connector() as connector:
                        engine = create_alloydb_engine(connector, catalog_db)
                        product_list = semantic_search.find_matching_products(
                            engine,
                            user_query,  # add image
                            catalog_table,
                            embedding_column,
                            row_count,
                        )
                        logging.info(f"product list returned by db: {product_list}")
                    if not product_list:
                        return (
                            jsonify({"error": "No matching products found"}),
                            404,
                        )
                    prompt = prompt_generation(user_query, product_list)
                    logging.info(f"Prompt used to re-rank: {prompt}")
                    reranked_result = rerank.query_pretrained_gemma(prompt)
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
        logging.error(f"An error occurred in backend application: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)  # Match the Service port
