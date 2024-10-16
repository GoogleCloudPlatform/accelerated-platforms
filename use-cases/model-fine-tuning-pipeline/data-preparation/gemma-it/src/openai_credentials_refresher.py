# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any

import os
import json
import logging
import logging.config
import google.auth
import google.auth.transport.requests
import openai

import tenacity

# Configure logging
logging.config.fileConfig("logging.conf")

logger = logging.getLogger("openaiauth")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)

from tenacity import retry, stop_after_attempt, wait_random


class OpenAICredentialsRefresher:
    def __init__(self, **kwargs: Any) -> None:
        logger.debug("Init openai credential refresher")
        # Set a dummy key here
        self.client = openai.OpenAI(**kwargs, api_key="DUMMY")
        self.creds, self.project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    @retry(wait=wait_random(min=5, max=10), stop=stop_after_attempt(3))
    def __getattr__(self, name: str) -> Any:
        try:
            if not self.creds.valid:
                auth_req = google.auth.transport.requests.Request()
                self.creds.refresh(auth_req)

                if not self.creds.valid:
                    print(f"Credentials invalid #2: {self.creds.valid}")
                    raise Exception

        except Exception as e:
            print(f"Unhandled exception from getter: {type(e).__name__}")
            logger.error(
                f"Unhandled exception from getter: {type(e).__name__}",
                exc_info=True,
            )
            raise

        self.client.api_key = self.creds.token
        return getattr(self.client, name)
