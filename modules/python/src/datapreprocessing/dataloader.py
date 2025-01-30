import pandas as pd
import logging


class DataLoader:
    """
    A class for loading data from Google Cloud Storage (GCS).

    Attributes:
        bucket_name (str): The name of the GCS bucket.
        file_path (str): The path to the file within the GCS bucket.
        logger (logging.Logger): A logger instance for logging messages.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, bucket_name, file_path):
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
