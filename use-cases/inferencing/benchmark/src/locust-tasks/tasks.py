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

from locust import FastHttpUser, run_single_user, task, between
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
    def __init__(self):  # Constructor
        self.model_id = os.environ["MODEL_ID"]
        self.endpoint = os.environ["ENDPOINT"]
        self.host = os.environ["HOST"]
        self.message1 = "I'm looking for comfortable cycling shorts for women, what are some good options?"
        self.message2 = "Tell me about some tops for men, looking for different styles"

    wait_time = between(1, 5)

    @task(50)
    def test1(self):
        headers = {"content-type": "application/json"}
        r = self.rest(
            "POST",
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
        print("FROM MESSAGE 1", r)

    @task(50)
    def test2(self):
        headers = {"content-type": "application/json"}
        r = self.rest(
            "POST",
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
        print("FROM MESSAGE 2", r)

    def benchmarks(self):
        # if "ACTION" in os.environ and os.environ["ACTION"] == "benchmark":
        #     self.test1()
        #     self.test2()
        self.test1()
        self.test2()


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
    benchmark_obj.benchmarks()
    # benchmark_obj.test1()
    # benchmark_obj.test2()