# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the data preparation ray_data_pipeline module."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from src.datapreparation.qa_generator import DATASET_COLUMNS, QA_COLUMNS, SPLITS
from src.datapreparation.ray_data_pipeline import (
    CATALOG_COLUMNS,
    PRODUCT_COLUMNS,
    RayDataPreparationPipeline,
    generate_qa_batch,
    keep_rows_with_values,
    select_listing,
    select_products,
    write_dataset_split,
)

try:
    import pyarrow

    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


def _catalog(rows):
    """Returns a PyArrow table of the processed product catalog."""
    schema = pyarrow.schema([(column, pyarrow.string()) for column in CATALOG_COLUMNS])
    return pyarrow.Table.from_pylist(
        [dict(zip(CATALOG_COLUMNS, row)) for row in rows], schema=schema
    )


def _products(rows):
    """Returns a PyArrow table of products."""
    schema = pyarrow.schema([(column, pyarrow.string()) for column in PRODUCT_COLUMNS])
    return pyarrow.Table.from_pylist(
        [dict(zip(PRODUCT_COLUMNS, row)) for row in rows], schema=schema
    )


@unittest.skipUnless(HAS_PYARROW, "pyarrow is not installed")
class TestBatchFunctions(unittest.TestCase):
    """Unit tests covering the functions that transform PyArrow batches."""

    def test_select_products(self):
        """Test that the products of the category and subcategories are selected."""
        batch = _catalog(
            [
                (
                    "Shirt ",
                    '{"Fit": "Slim"}',
                    "Clothing",
                    "Men's Clothing",
                    "Shirts",
                    "Casual",
                ),
                ("Boot", "{}", "Footwear", "Boots", "", ""),
                ("Cap", "{}", "Clothing", "Caps Clothing", "Caps", ""),
                ("Dress", None, "Clothing", "Women's Clothing", None, None),
            ]
        )

        products = select_products(
            batch, "Clothing", ["Women's Clothing", "Men's Clothing"]
        )

        self.assertEqual(products.column_names, PRODUCT_COLUMNS)
        self.assertEqual(
            products.to_pylist(),
            [
                {
                    "Name": "Shirt",
                    "Category": "Men's Clothing",
                    "Specifications": '{"Fit": "Slim"}',
                    "c2_name": "Shirts",
                    "c3_name": "Casual",
                },
                {
                    "Name": "Dress",
                    "Category": "Women's Clothing",
                    "Specifications": "",
                    "c2_name": "",
                    "c3_name": "",
                },
            ],
        )

    def test_select_products_empty(self):
        """Test that a batch without products of the category keeps the schema."""
        batch = _catalog([("Boot", "{}", "Footwear", "Boots", "", "")])
        products = select_products(batch, "Clothing", ["Men's Clothing"])

        self.assertEqual(products.num_rows, 0)
        self.assertEqual(products.schema, _products([]).schema)

    def test_keep_rows_with_values(self):
        """Test that only the rows with the values are kept."""
        batch = _products(
            [
                ("Shirt", "Men's Clothing", "{}", "Shirts", "Casual"),
                ("Tie", "Men's Clothing", "{}", "Ties", ""),
                ("Top", "Women's Clothing", "{}", "Tops", "Casual"),
            ]
        )

        kept = keep_rows_with_values(batch, "c2_name", ["Shirts", "Tops"])
        self.assertEqual(kept.column("Name").to_pylist(), ["Shirt", "Top"])
        self.assertEqual(kept.schema, batch.schema)

        kept = keep_rows_with_values(batch, "c3_name", [])
        self.assertEqual(kept.num_rows, 0)
        self.assertEqual(kept.schema, batch.schema)

    def test_select_listing(self):
        """Test that the listing with the most attributes is kept."""
        listings = [
            ("Shirt", "Men's Clothing", '{"Color": "Red"}', "Shirts", "Casual"),
            (
                "Shirt",
                "Men's Clothing",
                '{"Color": "Blue", "Fit": "Slim"}',
                "Shirts",
                "Casual",
            ),
            ("Shirt", "Men's Clothing", "", "Shirts", "Casual"),
        ]

        listing = select_listing(_products(listings))

        self.assertEqual(listing.schema, _products([]).schema)
        self.assertEqual(
            listing.column("Specifications").to_pylist(),
            ['{"Color": "Blue", "Fit": "Slim"}'],
        )

    def test_select_listing_is_independent_of_the_order(self):
        """Test that the same listing is kept in any order of the listings."""
        listings = [
            ("Shirt", "Men's Clothing", '{"Color": "Red"}', "Shirts", "Casual"),
            ("Shirt", "Men's Clothing", '{"Color": "Blue"}', "Shirts", "Casual"),
            ("Shirt", "Men's Clothing", '{"Color": "Green"}', "Shirts", "Formal"),
            ("Shirt", "Men's Clothing", '{"Color": "Blue"}', "Shirts", None),
        ]

        selected = {
            tuple(select_listing(_products(order)).to_pylist()[0].values())
            for order in (listings, listings[::-1], listings[2:] + listings[:2])
        }

        self.assertEqual(
            selected,
            {("Shirt", "Men's Clothing", '{"Color": "Blue"}', "Shirts", None)},
        )

    def test_generate_qa_batch(self):
        """Test that the pairs are generated for the products of a batch."""
        batch = _products(
            [
                ("Shirt", "Men's Clothing", '{"Fabric": "Cotton"}', "Shirts", "Casual"),
                ("Top", "Women's Clothing", "", "Tops", "Casual"),
            ]
        )

        pairs = generate_qa_batch(
            batch, num_questions=2, seed=42, train_ratio=0.8, validation_ratio=0.1
        )

        self.assertEqual(pairs.column_names, QA_COLUMNS)
        self.assertEqual(pairs.num_rows, 4)
        self.assertTrue(all(field.type == pyarrow.string() for field in pairs.schema))
        for row in pairs.to_pylist():
            self.assertIn(row["split"], SPLITS)
            self.assertTrue(row["prompt"].startswith("<start_of_turn>user\n"))

    def test_generate_qa_batch_empty(self):
        """Test that an empty batch generates an empty batch with the schema."""
        pairs = generate_qa_batch(
            _products([]),
            num_questions=3,
            seed=42,
            train_ratio=0.8,
            validation_ratio=0.1,
        )
        self.assertEqual(pairs.num_rows, 0)
        self.assertEqual(pairs.column_names, QA_COLUMNS)


class TestWriteDatasetSplit(unittest.TestCase):
    """Unit tests covering write_dataset_split."""

    def test_write_dataset_split(self):
        """Test that the split is saved in the Hugging Face datasets on disk format."""
        mock_datasets = MagicMock()
        mock_dataset = mock_datasets.Dataset.from_dict.return_value
        mock_dataset.num_rows = 2
        columns = {column: ["a", "b"] for column in DATASET_COLUMNS}
        columns["split"] = ["training", "training"]

        with patch.dict(sys.modules, {"datasets": mock_datasets}):
            rows = write_dataset_split(columns, "gs://bucket/dataset/output/training")

        self.assertEqual(rows, 2)
        written_columns = mock_datasets.Dataset.from_dict.call_args.args[0]
        self.assertEqual(list(written_columns), DATASET_COLUMNS)
        # The columns are written as text, also when the split is empty
        mock_datasets.Features.assert_called_once_with(
            {column: mock_datasets.Value.return_value for column in DATASET_COLUMNS}
        )
        mock_datasets.Value.assert_called_with("string")
        self.assertIs(
            mock_datasets.Dataset.from_dict.call_args.kwargs["features"],
            mock_datasets.Features.return_value,
        )
        mock_datasets.disable_progress_bar.assert_called_once()
        mock_dataset.save_to_disk.assert_called_once_with(
            "gs://bucket/dataset/output/training"
        )


class TestRayDataPreparationPipeline(unittest.TestCase):
    """Unit tests covering RayDataPreparationPipeline."""

    def _mock_ray(self, mock_ray, qa_pairs, product_count=2):
        """Configures the mocked ray module and returns the mocked dataset."""
        mock_ray.is_initialized.return_value = False
        mock_dataset = MagicMock()
        mock_ray.data.read_csv.return_value = mock_dataset
        mock_dataset.map_batches.return_value = mock_dataset
        mock_dataset.materialize.return_value = mock_dataset
        mock_dataset.count.return_value = product_count
        mock_dataset.take_all.return_value = qa_pairs

        def grouped(column):
            grouped_data = MagicMock()
            if isinstance(column, list):
                # The listings of each product
                grouped_data.map_groups.return_value = mock_dataset
            else:
                # The number of products of each category
                grouped_data.count.return_value.take_all.return_value = [
                    {column: "Shirts", "count()": 12},
                    {column: "Ties", "count()": 3},
                    {column: "", "count()": 50},
                ]
            self.grouped_data.append((column, grouped_data))
            return grouped_data

        self.grouped_data = []

        mock_dataset.groupby.side_effect = grouped
        # The write tasks return the number of rows of the split
        mock_ray.remote.return_value.remote.side_effect = lambda columns, uri: len(
            columns["Question"]
        )
        mock_ray.get.side_effect = lambda task: task
        return mock_dataset

    def _qa_pairs(self):
        return [
            {
                "Question": f"question {index}",
                "Answer": f"answer {index}",
                "Context": "context",
                "prompt": f"prompt {index}",
                "split": split,
            }
            for index, split in enumerate(
                ["training", "training", "validation", "test", "training"]
            )
        ]

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_execute(self, mock_ray):
        """Test that the dataset is prepared from and to Cloud Storage."""
        qa_pairs = self._qa_pairs()
        mock_dataset = self._mock_ray(mock_ray, qa_pairs + qa_pairs[:1])

        pipeline = RayDataPreparationPipeline(
            ray_cluster_host="local", ray_runtime_env={"pip": ["datasets"]}
        )
        summary = pipeline.execute(
            input_bucket="in-bucket",
            input_path="/processed/flipkart.csv",
            output_bucket="out-bucket",
            output_path="/dataset/output/",
        )

        self.assertEqual(
            summary,
            {
                "listings": 2,
                "products": 2,
                "qa_pairs": 5,
                "training": 3,
                "validation": 1,
                "test": 1,
            },
        )
        mock_ray.init.assert_called_once_with(runtime_env={"pip": ["datasets"]})
        self.assertEqual(
            mock_ray.data.read_csv.call_args.args[0],
            "gs://in-bucket/processed/flipkart.csv",
        )
        written_uris = sorted(
            call.args[1] for call in mock_ray.remote.return_value.remote.call_args_list
        )
        self.assertEqual(
            written_uris,
            [
                "gs://out-bucket/dataset/output/test",
                "gs://out-bucket/dataset/output/training",
                "gs://out-bucket/dataset/output/validation",
            ],
        )
        # Only the categories with enough products are kept, the empty category isn't
        category_filters = [
            call.kwargs["fn_kwargs"]["values"]
            for call in mock_dataset.map_batches.call_args_list
            if call.args[0] is keep_rows_with_values
        ]
        self.assertEqual(category_filters, [["Shirts"], ["Shirts"]])
        # One listing is kept for each product name and category
        column, grouped_data = self.grouped_data[-1]
        self.assertEqual(column, ["Name", "Category"])
        grouped_data.map_groups.assert_called_once_with(
            select_listing, batch_format="pyarrow"
        )
        mock_ray.shutdown.assert_called_once()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_options(self, mock_ray):
        """Test that the options of the dataset are passed to the batch functions."""
        mock_dataset = self._mock_ray(mock_ray, self._qa_pairs())

        RayDataPreparationPipeline().prepare(
            "input.csv",
            "output",
            num_questions=5,
            seed=7,
            category="Footwear",
            subcategories=("Men's Footwear",),
            min_category_count=3,
        )

        fn_kwargs = {
            call.args[0]: call.kwargs["fn_kwargs"]
            for call in mock_dataset.map_batches.call_args_list
        }
        self.assertEqual(
            fn_kwargs[select_products],
            {"category": "Footwear", "subcategories": ["Men's Footwear"]},
        )
        self.assertEqual(fn_kwargs[keep_rows_with_values]["values"], ["Shirts", "Ties"])
        self.assertEqual(
            fn_kwargs[generate_qa_batch],
            {
                "num_questions": 5,
                "seed": 7,
                "train_ratio": 0.8,
                "validation_ratio": 0.1,
            },
        )

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_without_products(self, mock_ray):
        """Test that an empty dataset isn't written when no products are selected."""
        self._mock_ray(mock_ray, [], product_count=0)

        with self.assertRaises(RuntimeError):
            RayDataPreparationPipeline("local").prepare("input.csv", "output")

        mock_ray.remote.return_value.remote.assert_not_called()
        mock_ray.shutdown.assert_called_once()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_catalog_without_columns(self, mock_ray):
        """Test that a catalog without the expected columns is explained."""
        mock_dataset = self._mock_ray(mock_ray, self._qa_pairs())
        mock_dataset.materialize.side_effect = Exception(
            "ArrowKeyError: Column 'product_name' in include_columns does not "
            "exist in CSV file"
        )

        with self.assertRaisesRegex(RuntimeError, "input.csv doesn't have the columns"):
            RayDataPreparationPipeline("local").prepare("input.csv", "output")

        mock_ray.remote.return_value.remote.assert_not_called()
        mock_ray.shutdown.assert_called_once()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_read_error(self, mock_ray):
        """Test that other errors of the read aren't changed."""
        mock_dataset = self._mock_ray(mock_ray, self._qa_pairs())
        mock_dataset.materialize.side_effect = FileNotFoundError("input.csv")

        with self.assertRaises(FileNotFoundError):
            RayDataPreparationPipeline("local").prepare("input.csv", "output")

        mock_ray.shutdown.assert_called_once()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_without_training_pairs(self, mock_ray):
        """Test that the dataset isn't written when the training split is empty."""
        qa_pairs = [pair for pair in self._qa_pairs() if pair["split"] != "training"]
        self._mock_ray(mock_ray, qa_pairs)

        with self.assertRaises(RuntimeError):
            RayDataPreparationPipeline("local").prepare("input.csv", "output")

        mock_ray.remote.return_value.remote.assert_not_called()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_invalid_configuration(self, mock_ray):
        """Test that an invalid configuration fails before connecting to Ray."""
        with self.assertRaises(ValueError):
            RayDataPreparationPipeline("local").prepare(
                "input.csv", "output", num_questions=0
            )
        mock_ray.init.assert_not_called()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_remote_cluster(self, mock_ray):
        """Test that the pipeline connects to a remote Ray cluster endpoint."""
        self._mock_ray(mock_ray, self._qa_pairs())

        RayDataPreparationPipeline("ray-head:10001").prepare("input.csv", "output")

        mock_ray.init.assert_called_once_with(
            address="ray://ray-head:10001", runtime_env=None
        )
        mock_ray.shutdown.assert_called_once()

    @patch("src.datapreparation.ray_data_pipeline.ray")
    def test_prepare_initialized_ray(self, mock_ray):
        """Test that an existing Ray session is reused and isn't shut down."""
        self._mock_ray(mock_ray, self._qa_pairs())
        mock_ray.is_initialized.return_value = True

        RayDataPreparationPipeline("local").prepare("input.csv", "output")

        mock_ray.init.assert_not_called()
        mock_ray.shutdown.assert_not_called()


if __name__ == "__main__":
    unittest.main()
