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

"""Ray Data pipeline orchestrator module for distributed, streaming data preprocessing."""

import logging
import os
import time
from typing import Any, Dict, Optional

import pandas as pd
import ray

try:
    from pyarrow import csv
except ImportError:
    from unittest.mock import MagicMock

    csv = MagicMock()
try:
    from ray.data.datasource import FilenameProvider
except (ImportError, ModuleNotFoundError):

    class FilenameProvider:
        """Fallback FilenameProvider base class when ray.data is mocked."""

        pass


logger = logging.getLogger(__name__)


def handle_invalid_row(row: Any) -> str:
    """Callback hook to skip malformed rows inside raw datasets safely during CSV parsing.

    Args:
        row: Row error context provided by PyArrow CSV parser.

    Returns:
        Action string instructing parser to 'skip' invalid rows.
    """
    return "skip"


class SingleFilenameProvider(FilenameProvider):
    """Custom filename generator to force a single, cleanly named output file footprint.

    This provider should only be used with Ray Datasets that have been repartitioned to 1 block.
    """

    def __init__(self, filename: str):
        """Initializes SingleFilenameProvider with target output filename.

        Args:
            filename: The target output filename (e.g., 'flipkart.csv').
        """
        self._filename = filename

    def get_filename_for_block(
        self,
        block: Any,
        task_index: int,
        block_index: int,
        shard_spec: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Returns the fixed single filename for the data block.

        Args:
            block: Ray Data block.
            task_index: Index of write task.
            block_index: Index of block.
            shard_spec: Optional shard specification.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The configured fixed target filename.
        """
        return self._filename


class PreprocessingActor:
    """Stateful worker pool for batch transformation in Ray Data pipeline."""

    def __init__(self, output_bucket: str, output_image_folder: str):
        """Initializes worker actors with DataPreprocessor and DataPrepForRag transformers.

        Args:
            output_bucket: Destination GCS bucket name.
            output_image_folder: Destination GCS subfolder for images.
        """
        from datapreprocessing.datacleaner import DataPrepForRag, DataPreprocessor

        self.preprocessor = DataPreprocessor()
        self.rag_transformer = DataPrepForRag()

        self.output_bucket = output_bucket
        self.output_image_folder = output_image_folder

    def __call__(self, batch: pd.DataFrame) -> pd.DataFrame:
        """Processes a pandas DataFrame batch through clean and RAG transformation stages.

        Args:
            batch: Input DataFrame batch from Ray Data.

        Returns:
            Processed and formatted DataFrame batch.
        """
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
    """Orchestrates streaming data pipelines using Ray Data engine."""

    def __init__(
        self,
        ray_cluster_host: Optional[str] = None,
        ray_runtime_env: Optional[Dict[str, Any]] = None,
    ):
        """Initializes RayDataPipelineOrchestrator with cluster host and runtime environment.

        Args:
            ray_cluster_host: Address of Ray cluster endpoint (e.g. 'ray://...' or 'local').
            ray_runtime_env: Runtime environment configuration passed to Ray tasks and actors.
        """
        self.ray_cluster_host = ray_cluster_host
        self.ray_runtime_env = ray_runtime_env

    def execute(
        self,
        input_bucket: str,
        input_path: str,
        output_bucket: str,
        output_path: str,
        output_image_folder: str,
    ) -> None:
        """Executes zero-copy GCS lazy reading, batch map transformation, and single-file CSV export.

        How Ray initialization is handled:
        - If Ray is already initialized in current context (e.g. Ray Job driver), it reuses session.
        - If `ray_cluster_host` is specified and not 'local', connects via `ray.init(address=...)`.
        - Otherwise, initializes a local Ray session if needed via `ray.init()`.

        Args:
            input_bucket: GCS bucket containing raw input file.
            input_path: File path within input_bucket.
            output_bucket: Destination GCS bucket for processed dataset.
            output_path: Destination path for output dataset.
            output_image_folder: Folder name in output_bucket for extracted images.
        """
        initialized_by_orchestrator = False

        if self.ray_cluster_host and self.ray_cluster_host != "local":
            os.environ["RAY_IGNORE_VERSION_MISMATCH"] = "1"
            target_address = self.ray_cluster_host
            if not target_address.startswith(
                "ray://"
            ) and not target_address.startswith("http://"):
                target_address = f"ray://{target_address}"

            logger.info(f"Connecting to GKE Ray Cluster endpoint via: {target_address}")
            ray.init(address=target_address, runtime_env=self.ray_runtime_env)
            initialized_by_orchestrator = True
        else:
            if not ray.is_initialized():
                logger.info(
                    "Running pipeline via localized cluster/driver tracking context..."
                )
                ray.init(runtime_env=self.ray_runtime_env)
                initialized_by_orchestrator = True

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
            """Filters required non-null columns from pandas batch."""
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

        # Coalesce the sharded data fragments into exactly 1 memory partition
        single_block_dataset = processed_dataset.repartition(1)

        # Step 4: Write output natively to GCS as a single, cleanly named CSV file
        single_block_dataset.write_csv(
            output_directory_uri,
            filename_provider=SingleFilenameProvider(target_filename),
        )

        duration = time.time() - start_time
        logger.info(f"Ray Data engine successfully finished in {duration:.2f} seconds")

        if initialized_by_orchestrator:
            ray.shutdown()
