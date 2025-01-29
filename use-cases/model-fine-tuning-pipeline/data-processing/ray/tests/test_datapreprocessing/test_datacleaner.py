import unittest
from unittest.mock import patch, Mock
import pandas as pd
from src.datapreprocessing.datacleaner import DataPreprocessor
import src.datapreprocessing.datacleaner


class TestDataCleaner(unittest.TestCase):
    def setUp(self):
        """Setup method to create a sample DataFrame and a DataPreprocessor instance."""
        self.df = pd.DataFrame(
            {
                "uniq_id": [1, 2, 3],
                "image": ['["url1"]', '["url2", "url3"]', None],
                "description": [
                    "This is a test description.",
                    "Another description.",
                    None,
                ],
                "product_specifications": [
                    '[{key1=>"value1", key2=>"value2"}]',
                    '[{"key3": "value3"}, {"key4": "value4"}]',
                    None,
                ],
                "product_category_tree": [
                    "Category A >> Category B",
                    "Category C",
                    None,
                ],
            }
        )
        self.cleaner = DataPreprocessor()

    def test_extract_url(self):
        """Test if image URLs are extracted correctly from the image column."""
        urls = self.cleaner.extract_url(self.df["image"][0])
        self.assertEqual(urls, ["url1"])
        urls = self.cleaner.extract_url(self.df["image"][1])
        self.assertEqual(urls, ["url2", " url3"])

    @patch("src.datapreprocessing.datacleaner.spacy.load")
    def test_prep_product_desc(self, mock_spacy_load):
        """Test if product descriptions are cleaned correctly."""
        mock_nlp = mock_spacy_load.return_value
        mock_nlp.return_value = [
            unittest.mock.Mock(lemma_="this", is_stop=True, is_alpha=True),
            unittest.mock.Mock(lemma_="be", is_stop=True, is_alpha=True),
            unittest.mock.Mock(lemma_="test", is_stop=False, is_alpha=True),
        ]
        cleaned_df = self.cleaner.prep_product_desc(self.df.copy())
        self.assertEqual(cleaned_df["description"][0], "test")

    def test_parse_attributes(self):
        """Test if product attributes are parsed correctly."""
        attributes = self.cleaner.parse_attributes(self.df["product_specifications"][0])
        self.assertEqual(attributes, '{"value1": "value2"}')
        attributes = self.cleaner.parse_attributes(self.df["product_specifications"][1])
        self.assertEqual(attributes, "{}")

    @patch("src.datapreprocessing.datacleaner.DataPreprocessor.download_image")
    def test_get_product_image(self, mock_download_image):
        """Test if product images are downloaded and URIs are updated."""

        def download_image_side_effect(*args, **kwargs):
            image_url = args  # Correctly access the first argument (url)
            if "url1" in image_url or "url2" in image_url:
                return True
            else:
                return False

        mock_download_image.side_effect = download_image_side_effect

        cleaned_df = self.cleaner.get_product_image(
            self.df.copy(), 1, "test_bucket", "test_path"
        )
        # Assertions
        self.assertEqual(
            len(cleaned_df["image_uri"]), 3
        )  # Check all rows have an image_uri (even if None)
        self.assertEqual(
            cleaned_df["image_uri"][0], f"gs://test/flipkart_images/1_0.jpg"
        )
        self.assertEqual(
            cleaned_df["image_uri"][1], f"gs://test/flipkart_images/2_0.jpg"
        )
        self.assertIsNone(cleaned_df["image_uri"][2])  # Check None when no image URL

        # Check the calls to download_image
        self.assertEqual(
            mock_download_image.call_count, 2
        )  # 1 for url1, 1 for url2/url3

    def test_reformat(self):
        """Test if the reformat method cleans the text correctly."""
        text = '[ "Test" ]'
        expected = " Test "
        self.assertEqual(self.cleaner.reformat(text), expected)

    def test_prep_cat(self):
        """Test if product categories are prepped correctly."""
        cleaned_df = self.cleaner.prep_cat(self.df.copy())
        self.assertEqual(cleaned_df["c0_name"][0], "Category A")
        self.assertEqual(cleaned_df["c1_name"][0], "Category B")

    @patch.object(
        src.datapreprocessing.datacleaner.DataPreprocessor, "get_product_image"
    )
    @patch.object(
        src.datapreprocessing.datacleaner.DataPreprocessor, "prep_product_desc"
    )
    @patch.object(src.datapreprocessing.datacleaner.DataPreprocessor, "prep_cat")
    def test_process_data(
        self, mock_get_product_image, mock_prep_product_desc, mock_prep_cat
    ):
        """Test the main process_data method."""
        mock_get_product_image.return_value = self.df.copy()
        mock_prep_product_desc.return_value = self.df.copy()
        mock_prep_cat.return_value = self.df.copy()
        cleaned_df = self.cleaner.process_data(
            self.df.copy(), 1, "test_bucket", "test_path"
        )
        self.assertEqual(len(cleaned_df), 3)


if __name__ == "__main__":
    unittest.main()
