# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
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

from datasets import load_dataset
from google.cloud import storage

# --- LOGGING CONFIGURATION ---
logging.config.fileConfig("logging.conf", disable_existing_loggers=True)
LOG = logging.getLogger(__name__)

# --- Configuration ---
DATASET_BUCKET_NAME = os.getenv("DATASET_BUCKET_NAME")
GCS_PREFIX = "gsm8k"
OUTPUT_FILENAME = "gsm8k_full.json"


def validate_config() -> None:
    """Validates that required environment variables are set.

    Raises:
        ValueError: If the DATASET_BUCKET_NAME environment variable is missing or empty.
    """
    if not DATASET_BUCKET_NAME:
        LOG.error("❌ Error: Environment variable 'DATASET_BUCKET_NAME' is not set.")
        raise ValueError("DATASET_BUCKET_NAME environment variable is required.")


def prepare_and_upload_dataset() -> None:
    """Downloads the GSM8K dataset from Hugging Face and uploads it to Google Cloud Storage.

    This function initializes a GCS client, attempts to fetch the GSM8K dataset
    from the Hugging Face hub, converts the records into a single JSON string,
    and uploads the resulting file to the configured GCS bucket.

    Raises:
        ValueError: If the specified GCS bucket does not exist or is inaccessible.
        Exception: If an error occurs during GCS client initialization, dataset
            download, or the final upload process.
    """
    validate_config()

    # 1. Initialize GCS Client
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(DATASET_BUCKET_NAME)
        if not bucket.exists():
            LOG.error(f"❌ Error: Bucket '{DATASET_BUCKET_NAME}' is not accessible.")
            raise ValueError(f"Bucket '{DATASET_BUCKET_NAME}' is not accessible.")
    except Exception as e:
        LOG.error(f"❌ Error connecting to GCS: {e}")
        raise e

    # 2. Load Dataset (GSM8K from Hugging Face)
    LOG.info("⬇️  Downloading dataset from Hugging Face...")
    try:
        # Loading the full 'main' split
        dataset = load_dataset("openai/gsm8k", "main", split="train")
    except Exception as e:
        LOG.info("Attempting alternative split loading...")
        dataset = load_dataset("openai/gsm8k", split="train")

    total_records = len(dataset)
    LOG.info(f"✅ Dataset loaded. Total records: {total_records}")

    # 3. Convert to List and Upload
    LOG.info(
        f"🚀 Uploading to gs://{DATASET_BUCKET_NAME}/{GCS_PREFIX}/{OUTPUT_FILENAME} ..."
    )

    try:
        # Convert the entire dataset to a list of dicts
        dataset_list = list(dataset)

        # Serialize to JSON
        json_data = json.dumps(dataset_list, indent=2)

        # Define GCS path
        blob_name = f"{GCS_PREFIX}/{OUTPUT_FILENAME}"
        blob = bucket.blob(blob_name)

        # Upload string directly to GCS
        blob.upload_from_string(data=json_data, content_type="application/json")
        LOG.info(f"✨ Successfully uploaded {total_records} records to {blob_name}")

    except Exception as e:
        LOG.error(f"❌ Failed to process or upload dataset: {e}")
        raise e


if __name__ == "__main__":
    prepare_and_upload_dataset()
