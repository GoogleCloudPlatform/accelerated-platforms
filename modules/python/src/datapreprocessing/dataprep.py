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
from typing import List

import pandas as pd


class DataPrep:
    """
    Prepares a Pandas DataFrame for further processing by splitting it into chunks and
    updating it based on specified columns and null value filtering.

    Attributes:
        df (pd.DataFrame): The input Pandas DataFrame.
        required_cols (list): A list of column names to keep in the DataFrame.
        filter_null_cols (list): A list of column names to check for null values.
        chunk_size (int, optional): The size of each chunk when splitting the DataFrame. Defaults to 199.
        logger (logging.Logger): A logger object for logging information and errors.

    Methods:
        split_dataframe(): Splits the DataFrame into chunks of a specified size.
        update_dataframe(): Updates the DataFrame by selecting required columns and dropping rows with null values.
    """

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        df: pd.DataFrame,
        required_cols: List[str],
        filter_null_cols: List[str],
        chunk_size: int = 199,
    ):
        """
        Initializes a DataPrep object.

        Args:
            df (pd.DataFrame): The input Pandas DataFrame.
            required_cols (list): A list of column names to keep.
            filter_null_cols (list): A list of column names to check for null values.
            chunk_size (int, optional): The size of each chunk. Defaults to 199.
        """
        self.df = df
        self.required_cols = required_cols
        self.filter_null_cols = filter_null_cols
        self.chunk_size = chunk_size

    def split_dataframe(self) -> List[pd.DataFrame]:
        """
        Splits the DataFrame into chunks of a specified size.

        Returns:
            list: A list of Pandas DataFrames, where each DataFrame is a chunk of the original DataFrame.
        """
        self.logger.info(f"Splitting dataframe into chunk size of '{self.chunk_size}'")
        chunks = list()
        num_chunks = len(self.df) // self.chunk_size + 1
        for i in range(num_chunks):
            chunks.append(self.df[i * self.chunk_size : (i + 1) * self.chunk_size])
        return chunks

    def update_dataframe(self) -> pd.DataFrame:
        """
        Updates the DataFrame by selecting only the required columns and dropping rows with null values
        in the specified columns.

        Returns:
            pd.DataFrame: The updated Pandas DataFrame.
        """
        self.df = self.df[self.required_cols]
        self.logger.info(f"Original dataset shape: '{self.df.shape}'")
        # Drop rows with null values in specified columns
        self.df.dropna(
            subset=self.filter_null_cols,
            inplace=True,
        )
        self.logger.info(f"After dropping null values: '{self.df.shape}'")
        return self.df
