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

import json
import logging
import logging.config
import os
import re
import signal
import sys

import pandas as pd
import requests
from datasets import load_from_disk
from google.cloud import storage


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


class Batch_Inference:
    def __init__(self):  # Constructor
        self.api_endpoint = os.environ["ENDPOINT"]
        self.model_name = os.environ["MODEL_PATH"]
        self.output_file = os.environ["PREDICTIONS_FILE"]
        self.gcs_bucket = os.environ["BUCKET"]
        self.dataset_output_path = os.environ["DATASET_OUTPUT_PATH"]
        test_dataset = load_from_disk(
            f"gs://{self.gcs_bucket}/{self.dataset_output_path}/test"
        )
        self.test_df = test_dataset.to_pandas()
        # Concatenate vertically (stack rows)
        self.df = pd.concat([self.test_df], axis=0)
        self.df.reset_index(drop=True, inplace=True)

    def predict(self):
        logger.info("Start predictions")
        # Send the Request
        headers = {"Content-Type": "application/json"}
        for i in range(len(self.df)):
            user_message = self.df["Question"][i]
            # Request Data
            request_data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": user_message}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            }
            # print(f"API Endpoint {self.api_endpoint}")
            response = requests.post(
                self.api_endpoint, headers=headers, data=json.dumps(request_data)
            )

            # Check for Successful Response
            if response.status_code == 200:
                response_data = response.json()
                # Assuming the response structure matches OpenAI's format
                ai_response = response_data["choices"][0]["message"]["content"]

                logger.info(
                    f"HTTP {response.status_code} received",
                    extra={
                        "ai_response": ai_response,
                        "user_message": user_message,
                    },
                )

                with open(self.output_file, "a") as f:
                    f.write(ai_response + "\n")  # Append with newline
                    f.write("----------\n")
            else:
                logger.error(f"Error: {response.status_code} - {response.text}")
        logger.info("Finish predictions")

        logger.info("Start write predictions to GCS")
        # save file to gcs after completion
        model_iteration_tag = self.model_name.rsplit("-", 1)[1]
        client = storage.Client()
        bucket = client.get_bucket(self.gcs_bucket)
        with open(self.output_file, "r") as local_file:
            blob = bucket.blob(f"predictions/{self.output_file}-{model_iteration_tag}")
            blob.upload_from_file(local_file)
        logger.info("Finish write predictions to GCS")

    def batchType(self):
        if "ACTION" in os.environ and os.getenv("ACTION") == "predict":
            self.predict()


if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")
    logger = logging.getLogger("batch_inference")

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

    inference = Batch_Inference()
    inference.batchType()
