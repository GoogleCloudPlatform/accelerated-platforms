import logging
import logging.config
import os
import sys
import signal
import numpy as np
from datapreprocessing.dataloader import DataLoader
from datapreprocessing.dataprep import DataPrep
from datapreprocessing.ray_utils import RayUtils
from datapreprocessing.datacleaner import DataPrepForRag

IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]
RAY_CLUSTER_HOST = os.environ["RAY_CLUSTER_HOST"]
# Check if this can be passed an env to the container like IMAGE_BUCKET
GCS_IMAGE_FOLDER = "flipkart_images"


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")
    logger = logging.getLogger(__name__)

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

    rag_preporcessing = DataPrepForRag()
    rag_df = rag_preporcessing.process_rag_input(result_df)
    # Store the rag preprocessed data into GCS
    rag_df.to_csv(
        "gs://" + IMAGE_BUCKET + rag_output_file,
        index=False,
    )
