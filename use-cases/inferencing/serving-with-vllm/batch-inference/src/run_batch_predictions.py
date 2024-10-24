import json
import logging
import logging.config
import os
import pandas as pd
import re
import sys
import requests
import signal

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
        self.df = pd.concat([self.validation_df, self.test_df], axis=0)
        self.df.reset_index(drop=True, inplace=True)

    def predict(self):
        logger.info("Start prediction evaluation")
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

                with open(self.output_file, "a") as f:
                    f.write(ai_response + "\n")  # Append with newline
                    f.write("----------\n")
            else:
                logger.error(f"Error: {response.status_code} - {response.text}")

        # save file to gcs after completion
        model_iteration_tag = self.model_name.rsplit("-", 1)[1]
        client = storage.Client()
        bucket = client.get_bucket(self.gcs_bucket)
        with open(self.output_file, "r") as local_file:
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
                    ground_truth["Answer"].str.contains(product_name, case=False)
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
