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

import concurrent.futures
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

# Seconds to wait for the answer of the model to a question
REQUEST_TIMEOUT_SECONDS = 600


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


class ModelEvaluation:
    def __init__(self):  # Constructor
        self.api_endpoint = os.environ["ENDPOINT"]
        self.model_name = os.environ["MODEL_PATH"]
        self.output_file = os.environ["PREDICTIONS_FILE"]
        self.gcs_bucket = os.environ["BUCKET"]
        self.dataset_output_path = os.environ["DATASET_OUTPUT_PATH"]
        # Number of requests that are sent to the model at the same time
        self.concurrent_requests = int(os.environ.get("CONCURRENT_REQUESTS", "32"))
        if self.concurrent_requests < 1:
            raise ValueError("CONCURRENT_REQUESTS must be at least 1")
        training_dataset = load_from_disk(
            f"gs://{self.gcs_bucket}/{self.dataset_output_path}/training"
        )
        validation_dataset = load_from_disk(
            f"gs://{self.gcs_bucket}/{self.dataset_output_path}/validation"
        )
        test_dataset = load_from_disk(
            f"gs://{self.gcs_bucket}/{self.dataset_output_path}/test"
        )
        # convert output to pandas dataframe
        self.training_df = training_dataset.to_pandas()
        self.validation_df = validation_dataset.to_pandas()
        self.test_df = test_dataset.to_pandas()
        # Concatenate vertically (stack rows)
        self.df = pd.concat([self.validation_df, self.test_df], axis=0).reset_index(
            drop=True
        )

    def get_prediction(self, user_message: str) -> str:
        """Sends a question to the model and returns the answer of the model."""
        headers = {"Content-Type": "application/json"}
        # Request Data
        request_data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": user_message}],
            "temperature": 0.5,
            "top_k": 1.0,
            "top_p": 1.0,
            # The longest answers of the test dataset have more than 256 tokens
            "max_tokens": 512,
        }
        response = requests.post(
            self.api_endpoint,
            headers=headers,
            data=json.dumps(request_data),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        # Check for Successful Response
        if response.status_code == 200:
            response_data = response.json()
            # Assuming the response structure matches OpenAI's format
            return response_data["choices"][0]["message"]["content"]

        logger.error(f"Error: {response.status_code} - {response.text}")
        # An empty prediction keeps the predictions aligned with the questions
        return ""

    def predict(self):
        logger.info("Start prediction evaluation")
        # The prompts of the training dataset have the context of the
        # conversation in front of the question
        user_messages = [
            f"Context:{context}\n{question}"
            for context, question in zip(self.df["Context"], self.df["Question"])
        ]
        # The requests are sent concurrently, and the inference server processes
        # them in batches. map() returns the predictions in the order of the
        # questions, whatever the order the requests complete in. When a request
        # raises an exception, for example because the inference server can't be
        # reached, the questions that are not sent yet are cancelled and the
        # exception ends the job before any prediction is written.
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.concurrent_requests
        ) as executor:
            predictions = list(executor.map(self.get_prediction, user_messages))

        with open(self.output_file, "w") as f:
            for ai_response in predictions:
                f.write(ai_response + "\n")
                f.write("----------\n")

        # save file to gcs after completion
        model_iteration_tag = self.model_name.rsplit("-", 1)[1]
        client = storage.Client()
        bucket = client.get_bucket(self.gcs_bucket)
        with open(self.output_file, "rb") as local_file:
            blob = bucket.blob(f"predictions/{self.output_file}-{model_iteration_tag}")
            blob.upload_from_file(local_file)

    # Function to extract product name from a line
    def extract_product_names(self, predictions_file: str) -> list[str]:
        product_names = []
        current_product = ""
        # Read and process the text file
        with open(predictions_file, "r") as file:
            for line in file:
                line = line.strip()
                # Check for the delimiter
                # if line == "Prompt:":
                if line == "----------":
                    if current_product:  # Ensure a product was found
                        product_names.append(current_product)
                    else:
                        product_names.append(
                            None
                        )  # When there is no product name in the prediction
                    current_product = ""  # Reset for the next product
                elif line.startswith("Product Name:"):
                    if not current_product:
                        current_product = line.split(": ")[1]
        return product_names

    # Function to extract the predictions, one for each question
    def extract_predictions(self, predictions_file: str) -> list[str]:
        predictions = []
        current_prediction = []
        with open(predictions_file, "r") as file:
            for line in file:
                # Check for the delimiter
                if line.strip() == "----------":
                    predictions.append("\n".join(current_prediction))
                    current_prediction = []  # Reset for the next prediction
                else:
                    current_prediction.append(line.rstrip("\n"))
        return predictions

    # Function to split an answer into its lines, product name and product details
    def parse_answer(self, answer: str) -> (list[str], str, set[str]):
        lines = [line.strip() for line in answer.splitlines() if line.strip()]
        product_name = None
        product_details = set()
        for line in lines:
            if line.startswith("Product Name:"):
                if not product_name:
                    product_name = line
            elif line.startswith("- "):
                product_details.add(line)
        return lines, product_name, product_details

    # Compare each prediction with the expected answer of its question
    def compare_with_expected_answers(
        self, predictions: list[str], expected_answers: list[str]
    ) -> dict[str, int]:
        comparison = {
            "correct_products": 0,
            "expected_details": 0,
            "correct_details": 0,
            "exact_answers": 0,
        }
        for prediction, expected_answer in zip(predictions, expected_answers):
            lines, product_name, details = self.parse_answer(prediction)
            expected_lines, expected_product_name, expected_details = self.parse_answer(
                expected_answer
            )
            if product_name and product_name == expected_product_name:
                comparison["correct_products"] += 1
            comparison["expected_details"] += len(expected_details)
            comparison["correct_details"] += len(details & expected_details)
            if lines == expected_lines:
                comparison["exact_answers"] += 1
        return comparison

    # This function counts no of predictions with no Product Names in it
    def count_no_products_prediction(self, product_names: list[str]) -> int:
        none_occurrences = [item for item in product_names].count(None)
        return none_occurrences

    # Count True Positives and False Positives
    def count_tp_fp(
        self, product_names: list[str], ground_truth: pd.DataFrame
    ) -> (int, int):
        true_positives_count = 0
        false_positives_count = 0
        for product_name in product_names:
            if product_name:
                # Option 1: Partial Match
                partial_match = ground_truth[
                    ground_truth["Answer"].str.contains(
                        re.escape(product_name), case=False
                    )
                ]
                if not partial_match.empty:
                    logger.info(f"Found partial matches for '{product_name}':")
                    true_positives_count += 1
                else:
                    # Option 2: Full Match (if partial match not found)
                    full_match = ground_truth[ground_truth["Answer"] == product_name]
                    if not full_match.empty:
                        logger.info(f"Found exact match for '{product_name}':")
                        true_positives_count += 1
                    else:
                        logger.info(
                            f"No match found for '{product_name}' in DataFrame."
                        )
                        false_positives_count += 1
        return true_positives_count, false_positives_count

    # Calculate Accuracy on Validation Dataset
    def calculate_accuracy(self):
        ground_truth = pd.DataFrame(self.training_df["Answer"])
        total_test_size = len(self.df)
        logger.info(f"Test dataset size: {total_test_size}")

        product_names = self.extract_product_names(self.output_file)

        true_positives_count, false_positives_count = self.count_tp_fp(
            product_names, ground_truth
        )
        none_predictions = self.count_no_products_prediction(product_names)
        logger.info(f"True Positives Count: {true_positives_count}")
        logger.info(f"False Positives Count: {false_positives_count}")
        logger.info(
            f"Number of predictions with no product details: {none_predictions}"
        )

        accuracy = round((true_positives_count / total_test_size) * 100, 2)
        logger.info(f"Accuracy of Gemma2 9B IT model on test dataset is {accuracy}%")

        if true_positives_count | false_positives_count:
            precision = round(
                (true_positives_count / (true_positives_count + false_positives_count))
                * 100,
                2,
            )
            logger.info(
                f"Precision of Gemma2 9B IT model on test dataset is {precision}%"
            )

        # Compare the predictions with the expected answers of the test dataset
        predictions = self.extract_predictions(self.output_file)
        if len(predictions) != total_test_size:
            logger.warning(
                f"Found {len(predictions)} predictions for {total_test_size} questions, "
                "unable to compare the predictions with the expected answers"
            )
            return

        comparison = self.compare_with_expected_answers(
            predictions, self.df["Answer"].tolist()
        )
        logger.info(f"Correct Products Count: {comparison['correct_products']}")
        logger.info(f"Exact Answers Count: {comparison['exact_answers']}")
        if comparison["expected_details"]:
            details_accuracy = round(
                (comparison["correct_details"] / comparison["expected_details"]) * 100,
                2,
            )
            logger.info(
                f"Product details accuracy of Gemma2 9B IT model on test dataset is {details_accuracy}%"
            )

    def evaluate(self):
        if "ACTION" in os.environ and os.environ["ACTION"] == "predict":
            self.predict()
        else:
            self.calculate_accuracy()


if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")
    logger = logging.getLogger("model_eval")

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

    model_eval = ModelEvaluation()
    model_eval.evaluate()
