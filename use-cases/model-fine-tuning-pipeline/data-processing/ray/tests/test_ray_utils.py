import unittest
import pandas as pd
from unittest.mock import patch, Mock
from src.datapreprocessing.ray_utils import RayUtils
import src.datapreporcessing


class TestRayUtils(unittest.TestCase):
    @patch("ray.get")
    @patch("importlib.import_module")
    def test_run_remote(self, mock_import_module, mock_ray_get):
        """Test if the run_remote method correctly invokes the remote tasks and returns the combined results."""
        mock_df = pd.DataFrame({"test": [1, 2, 3]})
        mock_ray_get.return_value = [
            pd.DataFrame({"test": [4]}),
            pd.DataFrame({"test": [5, 6]}),
        ]
        mock_module = Mock()
        mock_class = mock_module.DataPreprocessor.return_value
        mock_class.process_data.return_value = mock_df
        mock_import_module.return_value = mock_module

        ray_utils = RayUtils(
            ray_cluster_host="local",
            ray_resources={"cpu": 1},
            ray_runtime={"pip": ["pandas"]},
            package_name="datapreprocessing",
            module_name="datacleaner",
            class_name="DataPreprocessor",
            method_name="process_data",
            df=[pd.DataFrame({"test": [1]}), pd.DataFrame({"test": [2, 3]})],
            gcs_bucket="test",
        )
        result_df = ray_utils.run_remote()

        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(len(result_df), 3)
        mock_ray_get.assert_called()
        mock_import_module.assert_called_with("datapreprocessing.datacleaner")
        mock_class.process_data.assert_called()


if __name__ == "__main__":
    unittest.main()
