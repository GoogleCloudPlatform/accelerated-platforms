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
import time

import requests
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
# 1. Get the Shard Index (0-9) assigned by Kubernetes JobSet
JOB_INDEX = os.getenv("JOB_COMPLETION_INDEX", "0")

# 2. Get the Bucket Name from Environment Variable
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# 3. Define GCS Paths
PREFIX = "alpaca_shards"
INPUT_BLOB_NAME = f"{PREFIX}/input_shard_{JOB_INDEX}.json"
OUTPUT_BLOB_NAME = f"{PREFIX}/output_shard_{JOB_INDEX}.json"

# 4. Other Configurations
VLLM_API_ENDPOINT = os.getenv("VLLM_API_ENDPOINT", "http://localhost:8000")

# --- Setup Clients ---
# Initialize GCS Client
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


def validate_config():
    """
    Validates that all necessary environment variables are set.
    Exits the application if critical variables are missing.
    """
    LOG.info("\n🔍 Validating Configuration...")

    missing_vars = []

    # 1. Check Critical Variables (Must not be None or Empty)
    if not BUCKET_NAME:
        missing_vars.append("GCS_BUCKET_NAME")

    # 2. Hard Fail if missing
    if missing_vars:
        LOG.error(f"❌ FATAL ERROR: The following environment variables are missing:")
        for var in missing_vars:
            LOG.error(f"   - {var}")
        LOG.error("🛑 Exiting application.")
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # 3. Print Summary if successful
    LOG.info("✅ Configuration OK:")
    LOG.info(f"   - Bucket Name:         {BUCKET_NAME}")
    LOG.info("--------------------------------------------------\n")


def download_data():
    """Downloads the assigned shard from GCS to memory."""
    LOG.info(f"Worker {JOB_INDEX}: Downloading gs://{BUCKET_NAME}/{INPUT_BLOB_NAME}...")
    blob = bucket.blob(INPUT_BLOB_NAME)

    if not blob.exists():
        raise FileNotFoundError(f"Shard {INPUT_BLOB_NAME} not found in bucket.")

    json_data = blob.download_as_text()
    return json.loads(json_data)


def upload_results(results):
    """Uploads the inference results back to GCS."""
    LOG.info(
        f"Worker {JOB_INDEX}: Uploading results to gs://{BUCKET_NAME}/{OUTPUT_BLOB_NAME}..."
    )
    blob = bucket.blob(OUTPUT_BLOB_NAME)

    blob.upload_from_string(
        data=json.dumps(results, indent=2), content_type="application/json"
    )
    LOG.info("Upload complete.")


def wait_for_vllm():
    """Blocks until the vLLM sidecar is healthy."""
    LOG.info("Waiting for vLLM sidecar...")
    for _ in range(60):  # 10 minutes timeout (60 * 10s)
        try:
            resp = requests.get(f"{VLLM_API_ENDPOINT}/health")
            if resp.status_code == 200:
                LOG.info("vLLM is ready!")
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(10)
    raise RuntimeError("vLLM sidecar failed to start within timeout.")


def run_batch_inference(records):
    results = []
    total = len(records)

    # URL for the vLLM sidecar
    url = f"{VLLM_API_ENDPOINT}/v1/completions"  # e.g. http://localhost:8000/v1/completions
    headers = {"Content-Type": "application/json"}

    LOG.info(
        f"Worker {JOB_INDEX}: Starting inference on {total} records using raw HTTP."
    )

    for i, record in enumerate(records):
        prompt = (
            f"Instruction: {record['instruction']}\nInput: {record['input']}\nResponse:"
        )

        # Construct the raw JSON payload
        payload = {
            "prompt": prompt,
            "max_tokens": 128,
            "temperature": 0,
        }

        try:
            # Send raw POST request
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()  # Raise error for 4xx/5xx status codes

            # Parse JSON response
            # Structure matches OpenAI: {'choices': [{'text': '...', ...}], ...}
            response_json = response.json()
            completion = response_json["choices"][0]["text"].strip()

            results.append(
                {
                    "instruction": record["instruction"],
                    "input": record["input"],
                    "generated_response": completion,
                }
            )

            if i % 10 == 0:
                LOG.info(f"   Processed {i}/{total}")

        except Exception as e:
            LOG.warning(f"   ⚠️ Error on record {i}: {e}")

    return results


if __name__ == "__main__":
    # 0. Validate Configuration
    validate_config()

    # 1. Wait for Sidecar
    wait_for_vllm()

    # 2. Download Data from GCS
    data = download_data()

    # 3. Process
    results = run_batch_inference(data)

    # 4. Upload Results to GCS
    upload_results(results)

    LOG.info(f"Worker {JOB_INDEX}: Job Complete.")
