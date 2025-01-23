import unittest
import pandas as pd
from datapreprocessing.datacleaner import DataPreprocessor

class TestDataCleaner(unittest.TestCase):

    def setUp(self):
        """Setup method to create a sample DataFrame and a DataPreprocessor instance."""
        self.df = pd.DataFrame({
            'uniq_id': [1, 2, 3],
            'image': ['["url1"]', '["url2", "url3"]', None],
            'description': ['This is a test description.', 'Another description.', None],
            'product_specifications': ['[{"key1": "value1"}, {"key2": "value2"}]', '[{"key3": "value3"}]', None],
            'product_category_tree': ['Category A >> Category B', 'Category C', None],
        })
        self.cleaner = DataPreprocessor()

    def test_extract_url(self):
        """Test if image URLs are extracted correctly from the image column."""
        urls = self.cleaner.extract_url(self.df['image'][0])
        self.assertEqual(urls, ['url1'])
        urls = self.cleaner.extract_url(self.df['image'][1])
        self.assertEqual(urls, ['url2', 'url3'])

    def test_prep_product_desc(self):
        """Test if product descriptions are cleaned correctly."""
        with unittest.mock.patch('spacy.load') as mock_spacy_load:
            mock_nlp = mock_spacy_load.return_value
            mock_doc = mock_nlp.return_value = [
                unittest.mock.Mock(lemma_='this', is_stop=True, is_alpha=True),
                unittest.mock.Mock(lemma_='be', is_stop=True, is_alpha=True),
                unittest.mock.Mock(lemma_='test', is_stop=False, is_alpha=True),
            ]
            cleaned_df = self.cleaner.prep_product_desc(self.df.copy())
            self.assertEqual(cleaned_df['description'][0], 'test')

    def test_parse_attributes(self):
        """Test if product attributes are parsed correctly."""
        attributes = self.cleaner.parse_attributes(self.df['product_specifications'][0])
        self.assertEqual(attributes, '{"key1": "value1", "key2": "value2"}')

    def test_get_product_image(self):
        """Test if product images are downloaded and URIs are updated."""
        with unittest.mock.patch('google.cloud.storage.Client') as mock_storage_client:
            mock_bucket = mock_storage_client.return_value.bucket.return_value
            mock_blob = mock_bucket.blob.return_value
            mock_blob.upload_from_filename.return_value = None
            cleaned_df = self.cleaner.get_product_image(self.df.copy(), 1, "test")
            self.assertEqual(len(cleaned_df['image_uri']), 3)

    def test_reformat(self):
        """Test if the reformat method cleans the text correctly."""
        text = '[ "Test" ]'
        expected = ' Test  '
        self.assertEqual(self.cleaner.reformat(text), expected)

    def test_prep_cat(self):
        """Test if product categories are prepped correctly."""
        cleaned_df = self.cleaner.prep_cat(self.df.copy())
        self.assertEqual(cleaned_df['c0_name'][0], 'Category A')
        self.assertEqual(cleaned_df['c1_name'][0], 'Category B')

    def test_process_data(self):
        """Test the main process_data method."""
        with unittest.mock.patch('google.cloud.storage.Client'), \
             unittest.mock.patch.object(DataPreprocessor, 'get_product_image') as mock_get_product_image, \
             unittest.mock.patch.object(DataPreprocessor, 'prep_product_desc') as mock_prep_product_desc, \
             unittest.mock.patch.object(DataPreprocessor, 'prep_cat') as mock_prep_cat:

            mock_get_product_image.return_value = self.df.copy()
            mock_prep_product_desc.return_value = self.df.copy()
            mock_prep_cat.return_value = self.df.copy()

            cleaned_df = self.cleaner.process_data(self.df.copy(), 1, "test")
            self.assertEqual(len(cleaned_df), 3)

if __name__ == '__main__':
    unittest.main()