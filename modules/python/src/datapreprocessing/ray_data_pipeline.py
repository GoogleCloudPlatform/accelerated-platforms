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
import os
import time

import pandas as pd
import ray
from pyarrow import csv
from ray.data.datasource import FilenameProvider

# Configure structural logging layout
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def handle_invalid_row(row):
    """Callback hook to skip malformed rows inside raw datasets safely."""
    return "skip"


class SingleFilenameProvider(FilenameProvider):
    """Custom filename generator to force a single, cleanly named file footprint."""

    def __init__(self, filename: str):
        self._filename = filename

    # The exact block-level hook required by Ray's core engine
    def get_filename_for_block(
        self, block, task_index, block_index, shard_spec=None, *args, **kwargs
    ) -> str:
        return self._filename


class PreprocessingActor:
    """Stateful worker pool for Ray Data."""

    def __init__(self, output_bucket: str, output_image_folder: str):
        from datapreprocessing.datacleaner import DataPreprocessor, DataPrepForRag

        self.preprocessor = DataPreprocessor()
        self.rag_transformer = DataPrepForRag()

        self.output_bucket = output_bucket
        self.output_image_folder = output_image_folder

    def __call__(self, batch: pd.DataFrame) -> pd.DataFrame:
        try:
            worker_node_id = ray.get_runtime_context().get_node_id()
        except Exception:
            worker_node_id = "local-worker"

        cleaned_df = self.preprocessor.process_data(
            batch,
            ray_worker_node_id=worker_node_id,
            gcs_bucket=self.output_bucket,
            gcs_folder=self.output_image_folder,
        )

        rag_df = self.rag_transformer.process_rag_input(cleaned_df)
        return rag_df


class RayDataPipelineOrchestrator:
    """Replaces DataLoader, DataPrep, and RayUtils with a streaming data architecture."""

    def __init__(self, ray_cluster_host: str = None, ray_runtime_env: dict = None):
        self.ray_cluster_host = ray_cluster_host
        self.ray_runtime_env = ray_runtime_env

    def execute(
        self,
        input_bucket: str,
        input_path: str,
        output_bucket: str,
        output_path: str,
        output_image_folder: str,
    ):
        if self.ray_cluster_host and self.ray_cluster_host != "local":
            os.environ["RAY_IGNORE_VERSION_MISMATCH"] = "1"
            target_address = self.ray_cluster_host
            if not target_address.startswith(
                "ray://"
            ) and not target_address.startswith("http://"):
                target_address = f"ray://{target_address}"

            logger.info(f"Connecting to GKE Ray Cluster endpoint via: {target_address}")
            ray.init(address=target_address, runtime_env=self.ray_runtime_env)
        else:
            if not ray.is_initialized():
                logger.info(
                    "Running pipeline via localized cluster/driver tracking context..."
                )
                ray.init(runtime_env=self.ray_runtime_env)

        logger.info(
            "Ray streaming connection active. Initializing zero-copy GCS lazy read..."
        )
        start_time = time.time()

        input_uri = f"gs://{input_bucket}/{input_path.lstrip('/')}"

        target_output_path = output_path.lstrip("/")
        if target_output_path.endswith(".csv"):
            directory_path = os.path.dirname(target_output_path)
            target_filename = os.path.basename(target_output_path)
        else:
            directory_path = target_output_path
            target_filename = "flipkart.csv"

        output_directory_uri = f"gs://{output_bucket}/{directory_path}"
        logger.info(
            f"Targeting consolidated base output folder path: {output_directory_uri}"
        )

        custom_parse_options = csv.ParseOptions(
            newlines_in_values=True, invalid_row_handler=handle_invalid_row
        )

        # Step 1: Distributed read straight from Cloud Storage
        dataset = ray.data.read_csv(input_uri, parse_options=custom_parse_options)

        # Step 2: Global dataset pre-filtering
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

        def drop_null_records(df: pd.DataFrame) -> pd.DataFrame:
            valid_cols = [col for col in required_cols if col in df.columns]
            valid_filter_cols = [col for col in filter_null_cols if col in df.columns]
            return df[valid_cols].dropna(subset=valid_filter_cols).copy()

        filtered_dataset = dataset.map_batches(drop_null_records, batch_format="pandas")

        # Step 3: Stream batches dynamically through the stateful Actor processing loop
        processed_dataset = filtered_dataset.map_batches(
            PreprocessingActor,
            fn_constructor_kwargs={
                "output_bucket": output_bucket,
                "output_image_folder": output_image_folder,
            },
            compute=ray.data.ActorPoolStrategy(min_size=1, max_size=8),
            batch_size=200,
            batch_format="pandas",
        )

        logger.info(
            f"Coalescing data blocks down to single partition file: {target_filename}"
        )

        # Coalesce the 36 sharded data fragments into exactly 1 memory partition
        single_block_dataset = processed_dataset.repartition(1)

        # Step 4: Write output natively to GCS as a single, cleanly named CSV file
        single_block_dataset.write_csv(
            output_directory_uri,
            filename_provider=SingleFilenameProvider(target_filename),
        )

        duration = time.time() - start_time
        logger.info(f"Ray Data engine successfully finished in {duration:.2f} seconds")

        ray.shutdown()
