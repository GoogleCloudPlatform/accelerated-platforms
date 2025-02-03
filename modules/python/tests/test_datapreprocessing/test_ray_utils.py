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

import unittest
from unittest.mock import Mock, patch

import pandas as pd
import ray
import src.datapreprocessing.ray_utils


class TestRayUtils(unittest.TestCase):
    @patch.object(src.datapreprocessing.ray_utils.ray, "init")
    @patch("src.datapreprocessing.ray_utils.importlib.import_module")
    @patch.object(src.datapreprocessing.ray_utils.ray, "get")
    @patch.object(src.datapreprocessing.ray_utils.ray, "shutdown")
    def test_run_remote_local(
        self, mock_shutdown, mock_ray_get, mock_import_module, mock_ray_init
    ):
        """Test run_remote() with local Ray cluster."""
        # Mock necessary objects and functions
        mock_df = pd.DataFrame({"test": [1, 2, 3]})
        mock_ray_get.return_value = [
            pd.DataFrame({"test": [4]}),
            pd.DataFrame({"test": [5, 6]}),
        ]
        mock_module = Mock()
        mock_class = mock_module.DataPreprocessor.return_value
        mock_class.process_data.return_value = mock_df
        mock_import_module.return_value = mock_module
        # Initialize RayUtils
        ray_utils = src.datapreprocessing.ray_utils.RayUtils(
            ray_cluster_host="local",
            ray_resources={"cpu": 1},
            ray_runtime={"pip": ["pandas"]},
            package_name="datapreprocessing",
            module_name="datacleaner",
            class_name="DataPreprocessor",
            method_name="process_data",
            df=[pd.DataFrame({"test": [1]}), pd.DataFrame({"test": [2, 3]})],
            gcs_bucket="test_bucket",
            gcs_folder="test_path",
        )
        with patch.object(ray_utils.invoke_process_data, "remote") as mock_remote:
            mock_remote.return_value = mock_df  # Return a mock DataFrame
            result_df = ray_utils.run_remote()

        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(len(result_df), 3)
        mock_ray_init.assert_called_once()  # Ray initialized
        mock_import_module.assert_called_with(
            "datapreprocessing.datacleaner"
        )  # Module imported

        mock_ray_get.assert_called()  # ray.get called
        mock_remote.assert_called()  # invoke_process_data.remote called
        mock_shutdown.assert_called_once()  # Ray shutdown
