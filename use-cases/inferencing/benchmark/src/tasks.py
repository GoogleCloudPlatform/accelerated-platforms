#!/usr/bin/env python

# Copyright 2022 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from locust import FastHttpUser, task, between
import logging
import logging.config
import os
import signal
import requests


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


class MyUser(FastHttpUser):
    wait_time = between(5, 15)
    model_id = os.environ["MODEL_ID"]
    message1 = "I'm looking for comfortable cycling shorts for women, what are some good options?"
    message2 = "Tell me about some tops for men, looking for different styles"

    @task(20)
    def test1(self):
        headers = {"content-type": "application/json"}
        r = self.client.post(
            "/v1/chat/completions",
            json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": self.message1}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            headers=headers,
        )

    @task(75)
    def test2(self):
        headers = {"content-type": "application/json"}
        r = self.client.post(
            "/v1/chat/completions",
            json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": self.message2}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            headers=headers,
        )


if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")

    logger = logging.getLogger("benchmark_obj")

    if "LOG_LEVEL" in os.environ:
        new_log_level = os.environ["LOG_LEVEL"].upper()
        logger.info(
            f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
        )
        logging.getLogger().setLevel(new_log_level)
        logger.setLevel(new_log_level)

    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    benchmark_obj = MyUser()
