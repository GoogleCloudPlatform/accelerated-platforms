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

import google.api_core.exceptions
import google.auth
import google.auth.transport.requests
import sqlalchemy
from google.cloud.alloydb.connector import Connector, IPTypes

# AlloyDB
instance_uri = os.environ.get("MLP_DB_INSTANCE_URI")

# Use the application default credentials
# Kubernetes Service account impersonating as GCP account
credentials, project = google.auth.default()

auth_request = google.auth.transport.requests.Request()
credentials.refresh(auth_request)
user = credentials.service_account_email.removesuffix(".gserviceaccount.com")

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
    )
    logger.setLevel(new_log_level)


def init_connection_pool(
    connector: Connector,
    db: str,
) -> sqlalchemy.engine.Engine:
    """
    Initializes a SQLAlchemy engine for connecting to AlloyDB.
    """

    def getconn():
        logger.info("Creating connection to database '%s' as user '%s'", db, user)
        conn = connector.connect(
            db=db,
            driver="pg8000",
            enable_iam_auth=True,
            instance_uri=instance_uri,
            ip_type=IPTypes.PSC,
            user=user,
        )
        return conn

    # create connection pool
    pool = sqlalchemy.create_engine(
        creator=getconn,
        url="postgresql+pg8000://",
    )
    pool.dialect.description_encoding = None
    logger.info("Connection pool '%s' created successfully.", pool)
    return pool
