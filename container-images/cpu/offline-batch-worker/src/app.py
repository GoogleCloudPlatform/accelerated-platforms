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

import asyncio
import json
import logging
import logging.config
import os
import time

import aiohttp
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
DATASET_BUCKET_NAME = os.getenv("DATASET_BUCKET_NAME")

# 3. Define GCS Paths
PREFIX = "alpaca_shards"
INPUT_BLOB_NAME = f"{PREFIX}/input_shard_{JOB_INDEX}.json"
OUTPUT_BLOB_NAME = f"{PREFIX}/output_shard_{JOB_INDEX}.json"

# 4. Other Configurations
VLLM_API_ENDPOINT = os.getenv("VLLM_API_ENDPOINT", "http://localhost:8000")
# Controls how many requests we send to vLLM at once.
# Too high = OOM. Too low = GPU starvation. 100-200 is usually the sweet spot.
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "100"))

# --- Setup Clients ---
# Initialize GCS Client (Sync is fine for load/save)
storage_client = storage.Client()
bucket = storage_client.bucket(DATASET_BUCKET_NAME)


def validate_config():
    """
    Validates that all necessary environment variables are set.
    Exits the application if critical variables are missing.
    """
    LOG.info("\n🔍 Validating Configuration...")

    missing_vars = []

    # 1. Check Critical Variables (Must not be None or Empty)
    if not DATASET_BUCKET_NAME:
        missing_vars.append("DATASET_BUCKET_NAME")

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
    LOG.info(f"   - Bucket Name:         {DATASET_BUCKET_NAME}")
    LOG.info(f"   - Concurrency Level:   {CONCURRENT_REQUESTS}")
    LOG.info("--------------------------------------------------\n")


def download_data():
    """Downloads the assigned shard from GCS to memory."""
    LOG.info(
        f"Worker {JOB_INDEX}: Downloading gs://{DATASET_BUCKET_NAME}/{INPUT_BLOB_NAME}..."
    )
    blob = bucket.blob(INPUT_BLOB_NAME)

    if not blob.exists():
        raise FileNotFoundError(f"Shard {INPUT_BLOB_NAME} not found in bucket.")

    json_data = blob.download_as_text()
    return json.loads(json_data)


def upload_results(results):
    """Uploads the inference results back to GCS."""
    LOG.info(
        f"Worker {JOB_INDEX}: Uploading results to gs://{DATASET_BUCKET_NAME}/{OUTPUT_BLOB_NAME}..."
    )
    blob = bucket.blob(OUTPUT_BLOB_NAME)

    blob.upload_from_string(
        data=json.dumps(results, indent=2), content_type="application/json"
    )
    LOG.info("Upload complete.")


async def wait_for_vllm():
    """Blocks until the vLLM sidecar is healthy."""
    health_url = f"{VLLM_API_ENDPOINT}/health"
    
    LOG.info(f"Waiting for vLLM sidecar at {health_url}...")

    # Python 3.14 / aiohttp tip: Use a dedicated connector to handle fast-failing locals
    connector = aiohttp.TCPConnector(force_close=True)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(120):
            try:
                async with session.get(health_url, timeout=5) as resp:
                    if resp.status == 200:
                        LOG.info("✅ vLLM is ready!")
                        return
                    else:
                        LOG.info(f"   ... sidecar returned {resp.status}")
            except Exception as e:
                # Catch EVERYTHING during the wait phase.
                # We don't want the worker to die just because the sidecar isn't awake yet.
                if i % 6 == 0:
                    LOG.info(
                        f"   ... waiting for sidecar (Attempt {i}, last error: {type(e).__name__})"
                    )
            
            await asyncio.sleep(10)

    raise RuntimeError("vLLM sidecar failed to start within timeout.")


async def process_single_record(session, sem, record, index, total, url, headers):
    """
    Processes a single record asynchronously.
    Uses a semaphore to limit the number of concurrent requests.
    """
    async with sem:  # Wait for a slot to open in the semaphore
        prompt = (
            f"Instruction: {record['instruction']}\nInput: {record['input']}\nResponse:"
        )

        payload = {
            "prompt": prompt,
            "max_tokens": 128,
            "temperature": 0,
            # "model" field is optional for single-model vLLM instances
        }

        try:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                response_json = await response.json()
                completion = response_json["choices"][0]["text"].strip()

                # Log progress periodically (e.g., every 100 items)
                if index % 100 == 0:
                    LOG.info(f"   Processed {index}/{total}")

                return {
                    "instruction": record["instruction"],
                    "input": record["input"],
                    "generated_response": completion,
                }
        except Exception as e:
            LOG.warning(f"   ⚠️ Error on record {index}: {e}")
            return None  # Return None on failure, filter later


async def run_batch_inference_async(records):
    total = len(records)
    url = f"{VLLM_API_ENDPOINT}/v1/completions"
    headers = {"Content-Type": "application/json"}

    LOG.info(f"Worker {JOB_INDEX}: Starting ASYNC inference on {total} records.")
    LOG.info(f"Worker {JOB_INDEX}: Max concurrent requests: {CONCURRENT_REQUESTS}")

    # Create a semaphore to limit concurrency
    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    # Create the client session once and reuse it for all requests
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, record in enumerate(records):
            task = asyncio.create_task(
                process_single_record(session, sem, record, i, total, url, headers)
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)

    # Filter out failed requests (None values)
    successful_results = [r for r in results if r is not None]
    LOG.info(
        f"Worker {JOB_INDEX}: Finished. Success: {len(successful_results)}/{total}"
    )

    return successful_results


async def main():
    # 0. Validate Configuration
    validate_config()

    # 1. Wait for Sidecar (Async)
    await wait_for_vllm()

    # 2. Download Data from GCS (Sync, but fast enough)
    data = download_data()

    # --- DATA FORMAT FIX ---
    # Detect if data is a dictionary of lists (columnar) and convert to list of dicts (row-based)
    if isinstance(data, dict):
        LOG.info("⚠️ Detected columnar data format. Converting to list of rows...")
        keys = list(data.keys())
        # Assuming all columns have the same length, iterate by index
        data = [{k: data[k][i] for k in keys} for i in range(len(data[keys[0]]))]
        LOG.info(f"✅ Converted {len(data)} rows.")

    # 3. Process (Async)
    start_time = time.time()
    results = await run_batch_inference_async(data)
    duration = time.time() - start_time

    if duration > 0:
        LOG.info(f"⏱️ Speed: {len(results)/duration:.2f} requests/sec")

    # 4. Upload Results to GCS
    upload_results(results)

    LOG.info(f"Worker {JOB_INDEX}: Job Complete.")


if __name__ == "__main__":
    asyncio.run(main())
