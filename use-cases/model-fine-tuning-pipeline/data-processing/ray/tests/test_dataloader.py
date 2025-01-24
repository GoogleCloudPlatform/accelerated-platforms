import unittest
import pandas as pd
from unittest.mock import patch, Mock
from src.datapreprocessing.dataloader import DataLoader

class TestDataLoader(unittest.TestCase):

    @patch('google.cloud.storage.Client')
    def test_load_raw_data(self, mock_storage_client):
        """Test if the raw data is loaded correctly from the given bucket and file path."""
        mock_bucket = mock_storage_client.return_value.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.download_as_string.return_value = b'col1,col2\n1,2\n3,4'  # Mock CSV data

        bucket_name = 'test_bucket'
        file_path = 'test_path/test.csv'
        loader = DataLoader(bucket_name, file_path)
        df = loader.load_raw_data()

        mock_storage_client.assert_called_once_with()
        mock_bucket.blob.assert_called_once_with(file_path)
        mock_blob.download_as_string.assert_called_once_with()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)  # Check if the DataFrame was created correctly from the mock data

if __name__ == '__main__':
    unittest.main()