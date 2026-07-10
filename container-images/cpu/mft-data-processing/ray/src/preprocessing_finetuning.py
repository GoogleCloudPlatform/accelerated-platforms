# Copyright 2026 Google LLC
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

import logging
import logging.config
import os
import signal
import sys
from datapreprocessing.ray_data_pipeline import RayDataPipelineOrchestrator

# Target storage environments drawn from runtime system properties
DATASET_BUCKET = os.environ.get("DATASET_BUCKET", "trn-kr-ray-kaggle-accelerated-platforms-dev")
DATASET_FILE_PATH = os.environ.get("DATASET_FILE_PATH", "/datasets/PromptCloudHQ/flipkart-products/flipkart_com-ecommerce_sample.csv")

OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "trn-kr-ray-data-accelerated-platforms-dev")
OUTPUT_CSV_FILE_PATH = os.environ.get("OUTPUT_CSV_FILE_PATH", "/flipkart_preprocessed_dataset/flipkart.csv")
OUTPUT_IMAGE_FOLDER = os.environ.get("OUTPUT_IMAGE_FOLDER", "flipkart_images")

RAY_CLUSTER_HOST = os.environ.get("RAY_CLUSTER_HOST", "local")

# Configure logging at the module level safely
try:
    logging.config.fileConfig("logging.conf")
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def graceful_shutdown(signal_number, stack_frame):
    """Handles pipeline interruption cleanly."""
    signal_name = signal.Signals(signal_number).name
    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    sys.exit(0)


def preprocess_finetuning():
    """Preprocesses a raw dataset for fine-tuning a model using streaming Ray Data."""
    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Core environment context pushed directly to background cluster computation cells
    ray_runtime_env = {
        "py_modules": ["./datapreprocessing"],  # Dynamically zips and ships local modules to workers
        "pip": [
            "google-cloud-storage==2.19.0",
            "spacy==3.7.6",
            "jsonpickle==4.0.1",
            "pandas==2.2.3",
            "pydantic==2.10.5",
            "pyarrow",
            "gcsfs",
            "transformers==5.9.0",
            "diffusers==0.38.0"
        ],
        "env_vars": {
            "PIP_NO_CACHE_DIR": "1", 
            "PIP_DISABLE_PIP_VERSION_CHECK": "1"
        },
    }

    logger.info("Started Ray Data Streaming Infrastructure Pipeline")

    # Initialize the modern streaming pipeline wrapper orchestrator
    pipeline = RayDataPipelineOrchestrator(RAY_CLUSTER_HOST, ray_runtime_env)
    
    # Execute lazy loading, parallel computing blocks, and concurrent writing streams
    pipeline.execute(
        input_bucket=DATASET_BUCKET,
        input_path=DATASET_FILE_PATH,
        output_bucket=OUTPUT_BUCKET,
        output_path=OUTPUT_CSV_FILE_PATH,
        output_image_folder=OUTPUT_IMAGE_FOLDER  # FIXED: Passed down correctly now
    )
    
    logger.info("Distributed Ray Data Preprocessing Finished Successfully.")


if __name__ == "__main__":
    preprocess_finetuning()
