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

import google.auth
import google.auth.transport.requests
import logging
import openai
import os
import tenacity


from tenacity import retry, stop_after_attempt, wait_random


class OpenAICredentialsRefresher:
    def __init__(self, logger: logging, **kwargs: Any) -> None:
        self.logger = logger
        self.logger.debug("Init openai credential refresher")
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
                self.logger.debug(f"Refresh credentials")
                self.creds.refresh(auth_req)

                if not self.creds.valid:
                    self.logger.info(
                        f"Credentials invalid check #2: {self.creds.valid}"
                    )
                    raise Exception

        except Exception as e:
            self.logger.error(
                f"Unhandled exception from getter: {type(e).__name__}",
                exc_info=True,
            )
            raise

        self.client.api_key = self.creds.token
        return getattr(self.client, name)
