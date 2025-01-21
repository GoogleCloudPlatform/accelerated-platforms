import logging
import logging.config
import os
import signal
from datapreprocessing.dataloader import DataLoader
from datapreprocessing.dataprep import DataPrep
from datapreprocessing.ray_utils import RayUtils

IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]
RAY_CLUSTER_HOST = os.environ["RAY_CLUSTER_HOST"]
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

    # Instantiate RayUtils
    #ray_utils = RayUtils()

    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    #ray_utils.run_remote()

    ##new changes
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
            "pip": [
                "google-cloud-storage==2.16.0",
                "spacy==3.7.4",
                "jsonpickle==3.0.3",
                "pandas==2.2.1",
            ],
            "env_vars": {"PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        }
    chunk_size = 199
    module_name = "datacleaner"
    class_name = "DataPreprocessor"
    method_name = "process_data"

    data_loader = DataLoader(IMAGE_BUCKET, "flipkart_raw_dataset/flipkart_com-ecommerce_sample.csv")
    df = data_loader.load_raw_data()
    
    data_prep = DataPrep(df,required_cols,filter_null_cols,chunk_size)
    df = data_prep.update_dataframe()

    # Chunk the dataset
    res = data_prep.split_dataframe()

    # pass res to RayUtils object
    ray_obj = RayUtils(RAY_CLUSTER_HOST,res,ray_resources,ray_runtime_env,module_name,class_name,method_name)
    result_df = ray_obj.run_remote()
    # Replace NaN with None
    result_df = result_df.replace({np.nan: None})

    # Store the preprocessed data into GCS
    result_df.to_csv(
        "gs://" + IMAGE_BUCKET + "/flipkart_preprocessed_dataset/flipkart.csv",
        index=False,
    )