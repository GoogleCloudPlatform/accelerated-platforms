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

import pandas as pd


class DataLoader:
    """
    A class for loading data from Google Cloud Storage (GCS).

    Attributes:
        bucket_name (str): The name of the GCS bucket.
        file_path (str): The path to the file within the GCS bucket.
        logger (logging.Logger): A logger instance for logging messages.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, bucket_name: str, file_path: str):
        """
        Initializes a DataLoader object.

        Args:
            bucket_name (str): The name of the GCS bucket.
            file_path (str): The path to the file within the GCS bucket.
        """
        self.bucket_name = bucket_name
        self.file_path = file_path

    def load_raw_data(self) -> pd.DataFrame:
        """
        Loads raw data from GCS as a Pandas DataFrame.

        Returns:
            pandas.DataFrame: The loaded data.
        """
        self.logger.info(f"Downloading '{self.file_path}' from '{self.bucket_name}'")
        df = pd.read_csv(f"gs://{self.bucket_name}/{self.file_path}")
        return df
