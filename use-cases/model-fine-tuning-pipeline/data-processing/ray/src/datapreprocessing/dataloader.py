import pandas as pd
import logging


class DataLoader:

    logger = logging.getLogger(__name__)

    def __init__(self, bucket_name, file_path):
        self.bucket_name = bucket_name
        self.file_path = file_path

    def load_raw_data(self):
        """Loads raw data from GCS."""
        self.logger.info(f"Downloading '{self.file_path}' from '{self.bucket_name}'")
        df = pd.read_csv(f"gs://{self.bucket_name}/{self.file_path}")
        return df
