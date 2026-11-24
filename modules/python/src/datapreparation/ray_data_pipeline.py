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

"""Ray Data pipeline that prepares a fine-tuning dataset from the processed product catalog."""

import logging
import time
from typing import Any, Dict, Iterable, List, Optional

import ray

try:
    import pyarrow
    from pyarrow import csv
except ImportError:
    from unittest.mock import MagicMock

    pyarrow = MagicMock()
    csv = MagicMock()

from .qa_generator import (
    DATASET_COLUMNS,
    PRODUCT_CATEGORY_COLUMN,
    PRODUCT_NAME_COLUMN,
    PRODUCT_SPECIFICATIONS_COLUMN,
    QA_COLUMNS,
    SPLIT_TRAINING,
    SPLITS,
    QAGenerator,
    clean_text,
    finalize_qa_pairs,
    parse_specifications,
    split_qa_pairs,
)

logger = logging.getLogger(__name__)

# Columns of the processed product catalog that the pipeline reads
CATALOG_NAME_COLUMN = "product_name"
CATALOG_SPECIFICATIONS_COLUMN = "attributes"
CATALOG_CATEGORY_COLUMN = "c0_name"
CATALOG_SUBCATEGORY_COLUMN = "c1_name"
# Category levels that must have at least DEFAULT_MIN_CATEGORY_COUNT products
LOW_COUNT_CATEGORY_COLUMNS = ["c2_name", "c3_name"]
CATALOG_COLUMNS = [
    CATALOG_NAME_COLUMN,
    CATALOG_SPECIFICATIONS_COLUMN,
    CATALOG_CATEGORY_COLUMN,
    CATALOG_SUBCATEGORY_COLUMN,
] + LOW_COUNT_CATEGORY_COLUMNS

# Products used to build the dataset
DEFAULT_CATEGORY = "Clothing"
DEFAULT_SUBCATEGORIES = ("Women's Clothing", "Men's Clothing", "Kids' Clothing")
DEFAULT_MIN_CATEGORY_COUNT = 10

PRODUCT_COLUMNS = [
    PRODUCT_NAME_COLUMN,
    PRODUCT_CATEGORY_COLUMN,
    PRODUCT_SPECIFICATIONS_COLUMN,
] + LOW_COUNT_CATEGORY_COLUMNS


def _to_table(rows: List[Dict[str, str]], columns: List[str]) -> Any:
    """Converts rows to a PyArrow table of text columns.

    The schema is explicit so that every batch has the same schema, an empty
    batch included.
    """
    schema = pyarrow.schema([(column, pyarrow.string()) for column in columns])
    return pyarrow.Table.from_pylist(rows, schema=schema)


def select_products(batch: Any, category: str, subcategories: List[str]) -> Any:
    """Selects the products of a category from a batch of the product catalog.

    Args:
        batch: PyArrow table of the processed product catalog with the
            CATALOG_COLUMNS.
        category: Top level category of the products to select.
        subcategories: Subcategories of the products to select.

    Returns:
        PyArrow table of the selected products with the PRODUCT_COLUMNS.
    """
    products = []
    for row in batch.to_pylist():
        subcategory = clean_text(row[CATALOG_SUBCATEGORY_COLUMN])
        if (
            clean_text(row[CATALOG_CATEGORY_COLUMN]) != category
            or subcategory not in subcategories
        ):
            continue

        product = {
            PRODUCT_NAME_COLUMN: clean_text(row[CATALOG_NAME_COLUMN]),
            PRODUCT_CATEGORY_COLUMN: subcategory,
            PRODUCT_SPECIFICATIONS_COLUMN: row[CATALOG_SPECIFICATIONS_COLUMN] or "",
        }
        for column in LOW_COUNT_CATEGORY_COLUMNS:
            product[column] = clean_text(row[column])
        products.append(product)
    return _to_table(products, PRODUCT_COLUMNS)


def keep_rows_with_values(batch: Any, column: str, values: List[str]) -> Any:
    """Keeps the rows of a batch that have one of the values in a column.

    Args:
        batch: PyArrow table of products with the PRODUCT_COLUMNS.
        column: Column to check.
        values: Values of the rows to keep.

    Returns:
        PyArrow table of the rows kept.
    """
    values = set(values)
    return _to_table(
        [row for row in batch.to_pylist() if row[column] in values], PRODUCT_COLUMNS
    )


def select_listing(listings: Any) -> Any:
    """Selects one listing of a product that is listed more than once.

    The catalog lists some products several times with the same name and
    different specifications, for example once for each color. A question only
    names the product, so only one of the listings can be its answer.

    The listing with the most attributes is kept. Listings with the same number
    of attributes are compared by their content, so that the selection doesn't
    depend on the order of the listings.

    Args:
        listings: PyArrow table of the listings of a product with the
            PRODUCT_COLUMNS.

    Returns:
        PyArrow table of the listing kept.
    """
    listing = min(
        listings.to_pylist(),
        key=lambda listing: (
            -len(parse_specifications(listing[PRODUCT_SPECIFICATIONS_COLUMN])),
            [listing[column] or "" for column in PRODUCT_COLUMNS],
        ),
    )
    return _to_table([listing], PRODUCT_COLUMNS)


def generate_qa_batch(
    batch: Any,
    num_questions: int,
    seed: int,
    train_ratio: float,
    validation_ratio: float,
) -> Any:
    """Generates the question and answer pairs for a batch of products.

    Args:
        batch: PyArrow table of products with the PRODUCT_COLUMNS.
        num_questions: Number of question and answer pairs per product.
        seed: Seed for the question selection and the split assignment.
        train_ratio: Fraction of the pairs for the training split.
        validation_ratio: Fraction of the pairs for the validation split.

    Returns:
        PyArrow table with the QA_COLUMNS, one row per question and answer pair.
    """
    generator = QAGenerator(
        num_questions=num_questions,
        seed=seed,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
    )
    return _to_table(generator.generate(batch.to_pylist()), QA_COLUMNS)


def write_dataset_split(columns: Dict[str, List[str]], output_uri: str) -> int:
    """Writes a dataset split in the Hugging Face datasets on disk format.

    The fine-tuning and model evaluation steps load the splits with
    datasets.load_from_disk().

    Args:
        columns: DATASET_COLUMNS of the split, each column is a list of values.
        output_uri: Destination of the split (e.g. 'gs://bucket/path/training').

    Returns:
        Number of rows written.
    """
    # Imported here, the 'datasets' package is only required where the split is written
    import datasets
    from datasets import Dataset, Features, Value

    datasets.disable_progress_bar()

    features = Features({column: Value("string") for column in DATASET_COLUMNS})
    dataset = Dataset.from_dict(
        {column: columns[column] for column in DATASET_COLUMNS}, features=features
    )
    dataset.save_to_disk(output_uri)
    return dataset.num_rows


class RayDataPreparationPipeline:
    """Prepares the fine-tuning dataset from the processed product catalog with Ray Data.

    The pipeline selects the products of a category, removes the products of
    small categories, keeps one listing per product, generates question and
    answer pairs from templates and writes the training, validation and test
    splits.
    """

    def __init__(
        self,
        ray_cluster_host: Optional[str] = None,
        ray_runtime_env: Optional[Dict[str, Any]] = None,
    ):
        """Initializes the pipeline with the Ray cluster host and runtime environment.

        Args:
            ray_cluster_host: Address of the Ray cluster endpoint (e.g. 'ray://...'),
                or 'local' to use the Ray session of the current context.
            ray_runtime_env: Runtime environment for the Ray tasks.
        """
        self.ray_cluster_host = ray_cluster_host
        self.ray_runtime_env = ray_runtime_env

    def _init_ray(self) -> bool:
        """Connects to Ray, returns True if the connection was created here."""
        if self.ray_cluster_host and self.ray_cluster_host != "local":
            target_address = self.ray_cluster_host
            if not target_address.startswith(("ray://", "http://")):
                target_address = f"ray://{target_address}"

            logger.info(f"Connecting to the Ray cluster endpoint: {target_address}")
            ray.init(address=target_address, runtime_env=self.ray_runtime_env)
            return True

        if not ray.is_initialized():
            logger.info("Initializing Ray in the current context")
            ray.init(runtime_env=self.ray_runtime_env)
            return True

        return False

    def _materialize_products(self, products: Any, input_uri: str) -> Any:
        """Reads the product catalog and selects the products.

        Args:
            products: Ray dataset of the products selected from the catalog.
            input_uri: Location of the processed product catalog CSV file.

        Returns:
            The materialized Ray dataset.
        """
        try:
            return products.materialize()
        except Exception as error:
            # PyArrow reports the columns that it can't find in the CSV file
            if "include_columns" not in str(error):
                raise
            raise RuntimeError(
                f"{input_uri} doesn't have the columns of the processed product "
                f"catalog: {CATALOG_COLUMNS}. The file must be created by the data "
                "processing step of the same version as this data preparation."
            ) from error

    def _filter_low_count_categories(
        self, products: Any, column: str, min_count: int
    ) -> Any:
        """Removes the products of the categories that have less than min_count products.

        The products are counted across the whole dataset, not per batch.

        Args:
            products: Ray dataset of products.
            column: Category column to count the products by.
            min_count: Minimum number of products a category needs to be kept.

        Returns:
            The filtered Ray dataset.
        """
        counts = products.groupby(column).count().take_all()
        values = sorted(
            row[column] for row in counts if row[column] and row["count()"] >= min_count
        )
        logger.info(
            f"Keeping the products of {len(values)} of {len(counts)} '{column}' "
            f"categories with at least {min_count} products"
        )
        return products.map_batches(
            keep_rows_with_values,
            fn_kwargs={"column": column, "values": values},
            batch_format="pyarrow",
        )

    def _write_splits(
        self, splits: Dict[str, Dict[str, List[str]]], output_uri: str
    ) -> Dict[str, int]:
        """Writes the dataset splits in parallel with Ray tasks.

        Args:
            splits: Columns of each split.
            output_uri: Destination folder of the splits.

        Returns:
            Number of rows written for each split.
        """
        write_task = ray.remote(write_dataset_split)
        tasks = {
            split: write_task.remote(columns, f"{output_uri}/{split}")
            for split, columns in splits.items()
        }
        return {split: ray.get(task) for split, task in tasks.items()}

    def execute(
        self,
        input_bucket: str,
        input_path: str,
        output_bucket: str,
        output_path: str,
        **options: Any,
    ) -> Dict[str, int]:
        """Prepares the dataset from and to Cloud Storage.

        Args:
            input_bucket: Cloud Storage bucket of the processed product catalog.
            input_path: Path of the processed product catalog CSV file.
            output_bucket: Cloud Storage bucket for the dataset.
            output_path: Folder for the dataset splits.
            **options: Options of the dataset, see prepare().

        Returns:
            The counts returned by prepare().
        """
        return self.prepare(
            input_uri=f"gs://{input_bucket}/{input_path.lstrip('/')}",
            output_uri=f"gs://{output_bucket}/{output_path.strip('/')}",
            **options,
        )

    def prepare(
        self,
        input_uri: str,
        output_uri: str,
        num_questions: int = 6,
        seed: int = 42,
        train_ratio: float = 0.8,
        validation_ratio: float = 0.1,
        category: str = DEFAULT_CATEGORY,
        subcategories: Iterable[str] = DEFAULT_SUBCATEGORIES,
        min_category_count: int = DEFAULT_MIN_CATEGORY_COUNT,
    ) -> Dict[str, int]:
        """Reads the processed product catalog and writes the fine-tuning dataset.

        Args:
            input_uri: Location of the processed product catalog CSV file.
            output_uri: Folder for the dataset splits.
            num_questions: Number of question and answer pairs per product.
            seed: Seed for the question selection, the order and the splits.
            train_ratio: Fraction of the pairs for the training split.
            validation_ratio: Fraction of the pairs for the validation split, the
                remaining pairs are used for the test split.
            category: Top level category of the products to use.
            subcategories: Subcategories of the products to use.
            min_category_count: Minimum number of products that the lower level
                categories of a product need to have for the product to be used.

        Returns:
            Number of listings selected from the catalog, products, question
            and answer pairs, and rows written for each split.
        """
        # Fail before starting the pipeline if the configuration is invalid
        QAGenerator(
            num_questions=num_questions,
            seed=seed,
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
        )

        initialized_ray = self._init_ray()
        try:
            start_time = time.time()

            # Step 1: Distributed read of the processed product catalog. Only the
            # columns that are used are read, and they are read as text so that
            # the types aren't inferred from the first rows of the file.
            logger.info(f"Reading the processed product catalog from {input_uri}")
            catalog = ray.data.read_csv(
                input_uri,
                parse_options=csv.ParseOptions(newlines_in_values=True),
                convert_options=csv.ConvertOptions(
                    include_columns=CATALOG_COLUMNS,
                    column_types={
                        column: pyarrow.string() for column in CATALOG_COLUMNS
                    },
                ),
            )

            # Step 2: Select the products of the category
            products = catalog.map_batches(
                select_products,
                fn_kwargs={
                    "category": category,
                    "subcategories": list(subcategories),
                },
                batch_format="pyarrow",
            )

            # Step 3: Remove the products of small categories. The products are
            # materialized because they are read once to count the products of
            # the categories and once more to filter them.
            products = self._materialize_products(products, input_uri)
            for column in LOW_COUNT_CATEGORY_COLUMNS:
                products = self._filter_low_count_categories(
                    products, column, min_category_count
                ).materialize()
            listing_count = products.count()
            if listing_count == 0:
                raise RuntimeError(
                    f"No products selected from {input_uri}: it has no '{category}' "
                    "products of the subcategories, or all of them are in "
                    f"categories with less than {min_category_count} products. "
                    "Refusing to write an empty dataset."
                )

            # Step 4: Keep one listing of the products that are listed more than
            # once, so that every question has one answer
            products = (
                products.groupby([PRODUCT_NAME_COLUMN, PRODUCT_CATEGORY_COLUMN])
                .map_groups(select_listing, batch_format="pyarrow")
                .materialize()
            )
            product_count = products.count()
            logger.info(
                f"Selected {product_count} products from {listing_count} listings"
            )

            # Step 5: Generate the question and answer pairs
            qa_pairs = products.map_batches(
                generate_qa_batch,
                fn_kwargs={
                    "num_questions": num_questions,
                    "seed": seed,
                    "train_ratio": train_ratio,
                    "validation_ratio": validation_ratio,
                },
                batch_format="pyarrow",
            ).take_all()

            # Step 6: Put the pairs in a reproducible order and split the dataset
            qa_pairs = finalize_qa_pairs(qa_pairs, seed=seed)
            logger.info(f"Generated {len(qa_pairs)} question and answer pairs")
            splits = split_qa_pairs(qa_pairs)
            if not splits[SPLIT_TRAINING][DATASET_COLUMNS[0]]:
                raise RuntimeError(
                    "The training split is empty, refusing to write the dataset"
                )

            # Step 7: Write the splits
            logger.info(f"Writing the dataset splits to {output_uri}")
            written = self._write_splits(splits, output_uri)
            for split in SPLITS:
                logger.info(f"{split} data size: {written[split]}")

            duration = time.time() - start_time
            logger.info(f"Data preparation finished in {duration:.2f} seconds")

            return {
                "listings": listing_count,
                "products": product_count,
                "qa_pairs": len(qa_pairs),
                **written,
            }
        finally:
            if initialized_ray:
                ray.shutdown()
