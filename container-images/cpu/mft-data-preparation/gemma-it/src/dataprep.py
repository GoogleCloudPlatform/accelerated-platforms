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

import logging
import logging.config
import os
import signal
import sys

from datapreparation.ray_data_pipeline import RayDataPreparationPipeline

# The bucket which contains the processed data and receives the prepared dataset
BUCKET = os.environ.get("BUCKET")
DATASET_INPUT = os.environ.get("DATASET_INPUT_PATH", "flipkart_preprocessed_dataset")
DATASET_INPUT_FILE = os.environ.get("DATASET_INPUT_FILE", "flipkart.csv")
DATASET_OUTPUT = os.environ.get("DATASET_OUTPUT_PATH", "dataset/output")

# The number of questions and answers to generate for each product
NUM_QUESTIONS = int(os.environ.get("NUM_QUESTIONS", "6"))
# The seed of the dataset, the same seed always generates the same dataset
SEED = int(os.environ.get("SEED", "42"))

RAY_CLUSTER_HOST = os.environ.get("RAY_CLUSTER_HOST", "local")

# Configure logging at the module level safely. The loggers of the modules that
# are already imported are kept, the progress of the pipeline is logged by them.
try:
    logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

logger = logging.getLogger("processing")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    sys.exit(0)


def data_prep():
    """Prepares the dataset used to fine-tune the Gemma instruction tuned model.

    Reads the processed product catalog, generates question and answer pairs
    for the products from templates with Ray Data, and writes the training,
    validation and test splits to Cloud Storage.
    """
    if not BUCKET:
        raise ValueError("BUCKET environment variable must be set.")

    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Environment of the Ray tasks
    ray_runtime_env = {
        # Ship the local module to the Ray workers
        "py_modules": ["./datapreparation"],
        # The Ray cluster image doesn't contain these packages, so the Ray workers
        # install them when the job starts, as for the data processing. Remove the
        # list when the Ray cluster runs an image that contains the packages.
        # pyarrow is the lowest version that datasets accepts. The driver of the
        # job runs with pyarrow 23.0.1 of the Ray cluster image, and the tasks
        # can't read what the driver sends them when their version differs more.
        "pip": [
            "datasets==5.2.0",
            "gcsfs==2026.10.1",
            "pyarrow==24.0.0",
        ],
        "env_vars": {"PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
    }

    pipeline = RayDataPreparationPipeline(RAY_CLUSTER_HOST, ray_runtime_env)

    logger.info("Generate Q & A and prompts for the Gemma IT model")
    try:
        summary = pipeline.execute(
            input_bucket=BUCKET,
            input_path=f"{DATASET_INPUT}/{DATASET_INPUT_FILE}",
            output_bucket=BUCKET,
            output_path=DATASET_OUTPUT,
            num_questions=NUM_QUESTIONS,
            seed=SEED,
        )
    except Exception as e:
        logger.error(f"Data preparation failed: {e}", exc_info=True)
        sys.exit(1)

    logger.info(f"Prepared dataset uploaded to GCS: {summary}")


if __name__ == "__main__":
    logger.info("***Job Start***")
    data_prep()
    logger.info("***Job End***")
