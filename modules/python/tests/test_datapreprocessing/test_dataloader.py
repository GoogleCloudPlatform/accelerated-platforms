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

import csv
import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal
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
