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
import math
import os
import sys

from datasets import load_dataset
from google.cloud import storage

# --- LOGGING CONFIGURATION ---
ROOT_LEVEL = "INFO"
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Default is stderr
        },
    },
    "loggers": {
        "": {  # root logger
            "level": ROOT_LEVEL,  # "INFO",
            "handlers": ["default"],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "DEBUG",
            "handlers": ["default"],
        },
        "uvicorn.access": {
            "level": "DEBUG",
            "handlers": ["default"],
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)

LOG = logging.getLogger(__name__)

# --- Configuration ---
# Fetch bucket name from environment variable
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCS_PREFIX = "alpaca_shards"
NUM_SHARDS = 10


def validate_config():
    if not BUCKET_NAME:
        LOG.error("❌ Error: Environment variable 'GCS_BUCKET_NAME' is not set.")
        raise ValueError("GCS_BUCKET_NAME environment variable is required.")


def prepare_and_upload_shards():
    validate_config()

    # 1. Initialize GCS Client
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        # fast check if bucket exists (optional, but good for fail-fast)
        if not bucket.exists():
            LOG.error(
                f"❌ Error: Bucket '{BUCKET_NAME}' does not exist or you lack permissions."
            )
            raise ValueError(f"Bucket '{BUCKET_NAME}' is not accessible.")
    except Exception as e:
        LOG.error(f"❌ Error connecting to GCS: {e}")
        raise e

    # 2. Load Dataset (Alpaca Cleaned)
    LOG.info("⬇️  Downloading dataset from Hugging Face...")
    try:
        dataset = load_dataset("yahma/alpaca-cleaned", split="train")
    except Exception as e:
        LOG.error(f"❌ Error loading dataset: {e}")
        raise e

    total_records = len(dataset)
    shard_size = math.ceil(total_records / NUM_SHARDS)

    LOG.info(f"✅ Dataset loaded. Total records: {total_records}")
    LOG.info(f"⚡ Splitting into {NUM_SHARDS} shards of ~{shard_size} records each.")

    # 3. Shard and Upload
    LOG.info(f"🚀 Uploading to gs://{BUCKET_NAME}/{GCS_PREFIX}/ ...")

    for i in range(NUM_SHARDS):
        start_idx = i * shard_size
        end_idx = min((i + 1) * shard_size, total_records)
        shard_data = dataset[start_idx:end_idx]

        # Serialize to JSON
        json_data = json.dumps(shard_data, indent=2)

        # Define GCS path
        blob_name = f"{GCS_PREFIX}/input_shard_{i}.json"
        blob = bucket.blob(blob_name)

        try:
            # Upload string directly to GCS
            blob.upload_from_string(data=json_data, content_type="application/json")
            LOG.info(
                f"   • Uploaded shard {i}: {blob_name} ({len(shard_data)} records)"
            )
        except Exception as e:
            LOG.error(f"   ❌ Failed to upload shard {i}: {e}")
            raise e

    LOG.info("\n✨ All shards uploaded successfully.")


if __name__ == "__main__":
    prepare_and_upload_shards()
