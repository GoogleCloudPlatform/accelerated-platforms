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
import google.api_core.exceptions
import os
import sqlalchemy

from google.cloud.alloydb.connector import Connector, IPTypes

# AlloyDB
instance_uri = os.getenv("MLP_DB_INSTANCE_URI")

credentials, project = google.auth.default()
auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)

user = credentials.service_account_email.removesuffix(".gserviceaccount.com")
print.info(f"User: {user}")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("alloydb")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)


def init_connection_pool(connector: Connector, db: str) -> sqlalchemy.engine.Engine:
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
