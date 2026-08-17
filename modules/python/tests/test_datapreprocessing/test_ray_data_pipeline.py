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

"""Unit tests for ray_data_pipeline module."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from src.datapreprocessing.ray_data_pipeline import (
    PreprocessingActor,
    RayDataPipelineOrchestrator,
    SingleFilenameProvider,
    handle_invalid_row,
)


class TestRayDataPipeline(unittest.TestCase):
    """Unit tests covering SingleFilenameProvider, PreprocessingActor, and RayDataPipelineOrchestrator."""

    def test_handle_invalid_row(self):
        """Test that handle_invalid_row returns 'skip' for invalid CSV rows."""
        self.assertEqual(handle_invalid_row(None), "skip")
        self.assertEqual(handle_invalid_row("malformed_row"), "skip")

    def test_single_filename_provider(self):
        """Test that SingleFilenameProvider returns the configured target filename."""
        provider = SingleFilenameProvider("test_output.csv")
        filename = provider.get_filename_for_block(
            block=None, task_index=0, block_index=0
        )
        self.assertEqual(filename, "test_output.csv")

    @patch("datapreprocessing.datacleaner.storage.Client")
    @patch("datapreprocessing.datacleaner.DataPreprocessor.process_data")
    @patch("datapreprocessing.datacleaner.DataPrepForRag.process_rag_input")
    def test_preprocessing_actor(
        self, mock_rag, mock_process_data, mock_storage_client
    ):
        """Test PreprocessingActor batch transformation pipeline call."""
        df_input = pd.DataFrame(
            {
                "uniq_id": [1, 2],
                "description": ["desc1", "desc2"],
                "product_specifications": ["spec1", "spec2"],
                "product_category_tree": ["cat1 >> cat2", "cat3 >> cat4"],
                "image": ['["url1"]', '["url2"]'],
            }
        )
        mock_process_data.return_value = df_input
        mock_rag.return_value = pd.DataFrame({"Id": [1, 2]})

        actor = PreprocessingActor(
            output_bucket="test-bucket", output_image_folder="test-folder"
        )
        result = actor(df_input)

        self.assertIn("Id", result.columns)
        mock_process_data.assert_called_once()
        mock_rag.assert_called_once()

    @patch("src.datapreprocessing.ray_data_pipeline.ray")
    def test_orchestrator_execute_local(self, mock_ray):
        """Test RayDataPipelineOrchestrator execute method under local cluster settings."""
        mock_ray.is_initialized.return_value = False
        mock_dataset = MagicMock()
        mock_ray.data.read_csv.return_value = mock_dataset
        mock_dataset.map_batches.return_value = mock_dataset
        mock_dataset.repartition.return_value = mock_dataset

        orchestrator = RayDataPipelineOrchestrator(ray_cluster_host="local")
        orchestrator.execute(
            input_bucket="in-bucket",
            input_path="/path/input.csv",
            output_bucket="out-bucket",
            output_path="/path/out.csv",
            output_image_folder="img-folder",
        )

        mock_ray.init.assert_called_once()
        mock_ray.data.read_csv.assert_called_once()
        mock_dataset.write_csv.assert_called_once()
        mock_ray.shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
