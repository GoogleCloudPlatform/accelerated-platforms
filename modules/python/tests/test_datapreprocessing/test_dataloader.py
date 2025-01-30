import unittest
import pandas as pd
import os
import sys
from pandas.testing import assert_frame_equal
from unittest.mock import patch
import csv
from src.datapreprocessing.dataloader import DataLoader


class TestDataLoader(unittest.TestCase):
    @patch("src.datapreprocessing.dataloader.pd.read_csv")
    def test_load_raw_data(self, read_csv_mock):
        read_csv_mock.return_value = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        dataloader = DataLoader("fake_bucket", "fake_path")
        df = dataloader.load_raw_data()
        read_csv_mock.assert_called_with("gs://fake_bucket/fake_path")
        assert_frame_equal(df, read_csv_mock.return_value)


if __name__ == "__main__":
    unittest.main()
