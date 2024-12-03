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
import google.auth.iam
import google.auth.transport.requests
import logging
import logging.config
import os
import pg8000
import sqlalchemy
from google.cloud.alloydb.connector import Connector, IPTypes

# # Initialize credentials early to avoid redundant calls
# credentials, project = google.auth.default()
# auth_request = google.auth.transport.requests.Request()
# credentials.refresh(auth_request)

# # Store connection details in variables
# user = credentials.service_account_email.removesuffix(".gserviceaccount.com")
# password = credentials.token

# AlloyDb connnection

# instance_uri = os.environ("MLP_DB_INSTANCE_URI")
# alloydb_user = os.environ("MLP_DB_ADMIN_IAM")
instance_uri = "projects/gkebatchenv3a4ec43f/locations/us-central1/clusters/mlp-ishmeet-rag/instances/mlp-ishmeet-rag-primary"
alloydb_user = "wi-mlp-ishmeet-rag-db-admin@gkebatchenv3a4ec43f.iam"


# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("alloydb_connect")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)


def create_alloydb_engine(connector: Connector, catalog_db) -> sqlalchemy.engine.Engine:
    """
    Initializes a SQLAlchemy engine for connecting to AlloyDB.
    """

    def getconn() -> pg8000.dbapi.Connection:
        conn: pg8000.dbapi.Connection = connector.connect(
            instance_uri,
            "pg8000",
            user=alloydb_user,
            db=catalog_db,
            # TODO : Switch to PSC for GKE deployment
            ip_type=IPTypes.PUBLIC,
            enable_iam_auth=True,
        )
        return conn

    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    pool.dialect.description_encoding = None
    logger.info("Connection pool created successfully.")
    return pool


# connector = Connector()
# engine = create_alloydb_engine(connector, "product_catalog")
# sql = """
# SELECT column_name
# FROM information_schema.columns
# WHERE table_name = 'clothes'
# """
# connection = engine.connect()
# if connection:
#     print(connection)
#     result = connection.execute(sqlalchemy.text(sql))
#     for row in result:
#         print(row)
#     connection.close()
# connector.close()
