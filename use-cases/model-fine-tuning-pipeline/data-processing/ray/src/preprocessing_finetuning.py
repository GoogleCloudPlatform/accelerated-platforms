# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# https://www.apache.org/licenses/LICENSE-2.0

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

import numpy as np
from datapreprocessing.datacleaner import DataPrepForRag
from datapreprocessing.dataloader import DataLoader
from datapreprocessing.dataprep import DataPrep
from datapreprocessing.ray_utils import RayUtils

IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]
RAY_CLUSTER_HOST = os.environ["RAY_CLUSTER_HOST"]
# Check if this can be passed an env to the container like IMAGE_BUCKET
GCS_IMAGE_FOLDER = "flipkart_images"

# Configure logging at the module level
logging.config.fileConfig("logging.conf")
logger = logging.getLogger(__name__)

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
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


def preprocess_finetuning():
    """Preprocesses a raw dataset for fine-tuning a model.

    This function performs several steps to prepare data for fine-tuning, including:

    1. **Data Loading:** Loads raw data from a CSV file stored in Google Cloud Storage (GCS).
    2. **Data Cleaning:** Cleans and filters the data, selecting required columns and handling null values.
    3. **Data Chunking:** Splits the data into smaller chunks for parallel processing using Ray.
    4. **Download Images:** Uses Ray to distribute the data preprocessing task to download images.
    5. **Data Storage:** Stores the preprocessed data as a CSV file back to GCS.

    The function utilizes several global variables (e.g., `IMAGE_BUCKET`, `RAY_CLUSTER_HOST`, `GCS_IMAGE_FOLDER`) and relies on custom classes like `DataLoader`, `DataPrep`, and `RayUtils` for specific tasks.  It also configures signal handlers for graceful shutdown and sets up a Ray runtime environment with required Python modules and pip packages.

    Returns:
        None. The function saves the preprocessed data to a GCS location.
    """
    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    input_processing_file = "flipkart_raw_dataset/flipkart_com-ecommerce_sample.csv"
    output_processing_file = "/flipkart_preprocessed_dataset/flipkart.csv"
    rag_output_file = "/RAG/master_product_catalog.csv"
    required_cols = [
        "uniq_id",
        "product_name",
        "description",
        "brand",
        "image",
        "product_specifications",
        "product_category_tree",
    ]
    filter_null_cols = [
        "description",
        "image",
        "product_specifications",
        "product_category_tree",
    ]
    ray_resources = {"cpu": 1}
    ray_runtime_env = {
        "py_modules": ["./datapreprocessing"],  # Path to your module's directory
        "pip": [
            "google-cloud-storage==2.19.0",
            "spacy==3.7.6",
            "jsonpickle==4.0.1",
            "pandas==2.2.3",
            "pydantic==2.10.5",
        ],
        "env_vars": {"PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
    }
    chunk_size = 199
    # The following 4 parameters define which method to run as ray remote
    package_name = "datapreprocessing"
    module_name = "datacleaner"
    class_name = "DataPreprocessor"
    method_name = "process_data"

    logger.info("Started")
    data_loader = DataLoader(IMAGE_BUCKET, input_processing_file)
    df = data_loader.load_raw_data()

    data_prep = DataPrep(df, required_cols, filter_null_cols, chunk_size)
    df = data_prep.update_dataframe()

    # Chunk the dataset
    res = data_prep.split_dataframe()

    # create a RayUtils object with the info required to run a task
    ray_obj = RayUtils(
        RAY_CLUSTER_HOST,
        ray_resources,
        ray_runtime_env,
        package_name,
        module_name,
        class_name,
        method_name,
        res,
        IMAGE_BUCKET,
        GCS_IMAGE_FOLDER,
    )
    result_df = ray_obj.run_remote()
    # Replace NaN with None
    result_df = result_df.replace({np.nan: None})

    # Store the preprocessed data into GCS
    result_df.to_csv(
        "gs://" + IMAGE_BUCKET + output_processing_file,
        index=False,
    )
    logger.info("Finished")


if __name__ == "__main__":
    # Configure logging at the __main__ level
    logging.config.fileConfig("logging.conf")
    logger = logging.getLogger("preprocessing_finetuning")

    if "LOG_LEVEL" in os.environ:
        new_log_level = os.environ["LOG_LEVEL"].upper()
        logger.info(
            f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
        )
        logging.getLogger().setLevel(new_log_level)
        logger.setLevel(new_log_level)

    preprocess_finetuning()
