import unittest
import pandas as pd
from src.datapreprocessing.dataprep import DataPrep
import sys
import os


class TestDataPrep(unittest.TestCase):
    def setUp(self):
        """Setup method to create a sample DataFrame for testing."""
        self.df = pd.DataFrame(
            {
                "uniq_id": [1, 2, 3, 4, 5],
                "product_name": [
                    "Product A",
                    "Product B",
                    "Product C",
                    "Product D",
                    "Product E",
                ],
                "description": [
                    "Description A",
                    "Description B",
                    "Description C",
                    "Description D",
                    "Description E",
                ],
                "brand": ["Brand A", "Brand B", "Brand C", "Brand D", "Brand E"],
                "image": ["Image A", "Image B", "Image C", "Image D", "Image E"],
                "product_specifications": [
                    "Spec A",
                    "Spec B",
                    "Spec C",
                    "Spec D",
                    "Spec E",
                ],
                "product_category_tree": [
                    "Category A",
                    "Category B",
                    "Category C",
                    "Category D",
                    "Category E",
                ],
            }
        )

    def test_split_dataframe(self):
        """Test if the DataFrame is split correctly into chunks."""
        required_cols = [
            "uniq_id",
            "product_name",
            "description",
            "brand",
            "image",
            "product_specifications",
            "product_category_tree",
        ]
        filter_null_cols = [
            "description",
            "image",
            "product_specifications",
            "product_category_tree",
        ]
        data_prep = DataPrep(self.df, required_cols, filter_null_cols, chunk_size=2)
        chunks = data_prep.split_dataframe()
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 2)
        self.assertEqual(len(chunks[1]), 2)
        self.assertEqual(len(chunks[2]), 1)

    def test_update_dataframe(self):
        """Test if the DataFrame is updated correctly by dropping rows with null values."""
        required_cols = [
            "uniq_id",
            "product_name",
            "description",
            "brand",
            "image",
            "product_specifications",
            "product_category_tree",
        ]
        filter_null_cols = [
            "description",
            "image",
            "product_specifications",
            "product_category_tree",
        ]
        data_prep = DataPrep(self.df, required_cols, filter_null_cols, chunk_size=2)
        updated_df = data_prep.update_dataframe()
        self.assertEqual(len(updated_df), 5)

        # Introduce a null value
        self.df.loc[0, "description"] = None
        data_prep = DataPrep(self.df, required_cols, filter_null_cols, chunk_size=2)
        updated_df = data_prep.update_dataframe()
        self.assertEqual(len(updated_df), 4)  # One row should be dropped


if __name__ == "__main__":
    unittest.main()
