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

"""Data cleaning and preprocessing routines for Ray data processing workflows."""

import logging
import os
import re
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import List

import jsonpickle
import pandas as pd
import ray
from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY

try:
    import spacy
except ImportError:
    from unittest.mock import MagicMock

    spacy = MagicMock()


class DataPreprocessor:
    """Optimized preprocessing utility designed for parallel Ray environments."""

    logger = logging.getLogger(__name__)

    def __init__(self):
        """Initializes the DataPreprocessor instance, GCS client, thread pool, and spaCy NLP pipeline."""
        # 1. Instantiate the storage client ONCE per worker process initialization
        self.storage_client = storage.Client()

        # 2. Dynamic Approach: Eliminate magic thread numbers by checking Ray allocations
        try:
            # Query how many CPU cores Ray allocated specifically to this actor instance container
            assigned_cpus = (
                ray.get_runtime_context().get_assigned_resources().get("CPU", 1)
            )
            # For network I/O intensive routines (image downloading), 10 threads per CPU core is optimal
            self.max_workers = max(10, int(assigned_cpus * 10))
            self.logger.info(
                f"Dynamically initialized ThreadPool with {self.max_workers} workers based on {assigned_cpus} Ray CPUs."
            )
        except Exception:
            # Fallback scaling rule if code is executed outside a cluster worker thread context
            cores = os.cpu_count() or 1
            self.max_workers = min(32, cores * 5)
            self.logger.info(
                f"Fallback context: Initialized {self.max_workers} threads based on system CPU core count ({cores})."
            )

        # 3. Load or download the spaCy model ONCE per worker process initialization
        self.nlp = None
        if spacy is not None:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                self.logger.info(
                    "Downloading spacy model 'en_core_web_sm' on worker process..."
                )
                spacy.cli.download("en_core_web_sm")
                self.nlp = spacy.load("en_core_web_sm")

    def extract_url(self, image_list: str) -> List[str]:
        """Extracts individual image URLs from a formatted string or list representation.

        Args:
            image_list: Raw string representation of an image URL list.

        Returns:
            List of parsed image URL strings.
        """
        if pd.isna(image_list):
            return []
        return image_list.replace("[", "").replace("]", "").replace('"', "").split(",")

    def download_image(
        self,
        image_url: str,
        image_file_name: str,
        destination_blob_name: str,
        ray_worker_node_id: str,
        gcs_bucket: str,
    ) -> bool:
        """Downloads an image from a URL and uploads it to Google Cloud Storage.

        Args:
            image_url: Source URL of the image to download.
            image_file_name: Temporary local filename for saving the download.
            destination_blob_name: Target path/blob name in the GCS bucket.
            ray_worker_node_id: Identifier of the current Ray worker node for logging.
            gcs_bucket: Name of the destination GCS bucket.

        Returns:
            True if the image was successfully downloaded and uploaded, False otherwise.
        """
        download_dir = "/tmp/images"
        os.makedirs(download_dir, exist_ok=True)
        download_file = f"{download_dir}/{image_file_name}"

        # 1. Attempt Download
        try:
            socket.setdefaulttimeout(5)
            urllib.request.urlretrieve(image_url, download_file)
        except Exception as err:
            self.logger.warning(
                f"ray_worker_node_id:{ray_worker_node_id} Failed to download image {image_url}: {err}"
            )
            if os.path.exists(download_file):
                os.remove(download_file)
            return False

        # 2. Attempt Upload
        try:
            bucket = self.storage_client.bucket(gcs_bucket)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_filename(download_file, retry=DEFAULT_RETRY)
        except Exception as err:
            self.logger.warning(
                f"ray_worker_node_id:{ray_worker_node_id} Failed to upload image {destination_blob_name} to GCS: {err}"
            )
            if os.path.exists(download_file):
                os.remove(download_file)
            return False

        # Cleanup on success
        try:
            os.remove(download_file)
        except OSError as err:
            self.logger.debug(f"Failed to remove temp file {download_file}: {err}")

        return True

    def _process_single_row_image(
        self, row: dict, ray_worker_node_id: str, gcs_bucket: str, gcs_folder: str
    ) -> str:
        """Helper processing callback targeted by the asynchronous thread pool.

        Args:
            row: Dictionary representing a single record/row in the dataset.
            ray_worker_node_id: Identifier of the current Ray worker node.
            gcs_bucket: Destination GCS bucket name.
            gcs_folder: Destination directory path inside the GCS bucket.

        Returns:
            The GCS URI (gs://...) of the first successfully uploaded image, or None.
        """
        prod_id = row.get("uniq_id")
        image_list = row.get("image")

        if pd.isnull(image_list):
            return None

        image_urls = self.extract_url(image_list)
        for index, url in enumerate(image_urls):
            url_clean = url.strip()
            if not url_clean:
                continue

            image_file_name = f"{prod_id}_{index}.jpg"
            destination_blob_name = f"{gcs_folder}/{prod_id}_{index}.jpg"

            success = self.download_image(
                url_clean,
                image_file_name,
                destination_blob_name,
                ray_worker_node_id,
                gcs_bucket,
            )
            if success:
                return f"gs://{gcs_bucket}/{destination_blob_name}"
        return None

    def get_product_image(
        self,
        df: pd.DataFrame,
        ray_worker_node_id: str,
        gcs_bucket: str,
        gcs_folder: str,
    ) -> pd.DataFrame:
        """Downloads product images in parallel for a batch and appends GCS image URIs.

        Args:
            df: Input DataFrame containing product records.
            ray_worker_node_id: Identifier of the current Ray worker node.
            gcs_bucket: Name of the destination GCS bucket.
            gcs_folder: Destination subfolder in the GCS bucket.

        Returns:
            DataFrame with an added 'image_uri' column containing GCS image paths.
        """
        # Convert the batch chunks cleanly to records for thread-safe isolation
        records = df.to_dict(orient="records")

        # Parallelize downloading across the dynamic, calculated thread limits
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(
                    self._process_single_row_image,
                    row,
                    ray_worker_node_id,
                    gcs_bucket,
                    gcs_folder,
                )
                for row in records
            ]
            gcs_image_urls = [f.result() for f in futures]

        df["image_uri"] = gcs_image_urls
        return df

    def prep_product_desc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cleans product description text using spaCy NLP lemmatization and stop-word removal.

        Args:
            df: Input DataFrame containing a 'description' column.

        Returns:
            DataFrame with cleaned/lemmatized 'description' column.
        """

        def parse_nlp_description(description: str) -> str:
            if not description or pd.isna(description) or not self.nlp:
                return "None"
            try:
                doc = self.nlp(str(description).lower())
                lemmas = [
                    token.lemma_
                    for token in doc
                    if not token.is_stop and token.is_alpha
                ]
                return " ".join(dict.fromkeys(lemmas))
            except Exception:
                return "None"

        df["description"] = df["description"].apply(parse_nlp_description)
        return df

    def parse_attributes(self, specification: str) -> str:
        """Parses raw product specification strings into JSON-encoded key-value key attributes.

        Args:
            specification: Raw product specification string.

        Returns:
            JSON-encoded string representing the key-value attribute dictionary.
        """
        spec_match_one = re.compile("(.*?)\\[(.*)\\](.*)")
        spec_match_two = re.compile('(.*?)=>"(.*?)"(.*?)=>"(.*?)"(.*)')
        if pd.isna(specification):
            return jsonpickle.encode({})

        m = spec_match_one.match(str(specification))
        out = {}
        if m is not None and m.group(2) is not None:
            phrase = ""
            for c in m.group(2):
                if c == "}":
                    m2 = spec_match_two.match(phrase)
                    if m2 and m2.group(2) is not None and m2.group(4) is not None:
                        out[m2.group(2)] = m2.group(4)
                    phrase = ""
                else:
                    phrase += c
        return jsonpickle.encode(out)

    def reformat(self, text: str) -> str:
        """Strips bracket and quote formatting characters from raw category strings.

        Args:
            text: Raw input string containing bracket or quote characters.

        Returns:
            Cleaned text string.
        """
        if pd.isnull(text):
            return ""
        return str(text).replace("[", "").replace("]", "").replace('"', "")

    def prep_cat(self, df: pd.DataFrame) -> pd.DataFrame:
        """Splits category hierarchy trees into static categorical columns (c0_name .. c5_name).

        Args:
            df: Input DataFrame with a 'product_category_tree' column.

        Returns:
            DataFrame with split category columns and original tree dropped.
        """
        df["product_category_tree"] = df["product_category_tree"].apply(self.reformat)
        splits = df["product_category_tree"].str.split(">>")

        # Enforce exactly 6 static categorical dimensions to prevent cross-batch schema errors
        max_levels = 6
        for i in range(max_levels):
            df[f"c{i}_name"] = splits.apply(
                lambda x: x[i].strip() if isinstance(x, list) and len(x) > i else ""
            )

        df = df.drop("product_category_tree", axis=1)
        return df

    def process_data(
        self,
        df: pd.DataFrame,
        ray_worker_node_id: str,
        gcs_bucket: str,
        gcs_folder: str,
    ) -> pd.DataFrame:
        """Executes full cleaning pipeline sequence (images, descriptions, attributes, categories).

        Args:
            df: Raw input DataFrame.
            ray_worker_node_id: Current Ray worker node identifier.
            gcs_bucket: Destination GCS bucket name for image storage.
            gcs_folder: Subfolder path in the GCS bucket.

        Returns:
            Fully cleaned and preprocessed DataFrame.
        """
        df_processed = self.get_product_image(
            df, ray_worker_node_id, gcs_bucket, gcs_folder
        )
        df_processed = self.prep_product_desc(df_processed)
        df_processed["attributes"] = df_processed["product_specifications"].apply(
            self.parse_attributes
        )
        df_processed = df_processed.drop("product_specifications", axis=1)
        df_processed = self.prep_cat(df_processed)
        return df_processed


class DataPrepForRag:
    """Filters and structures pipeline inputs explicitly for RAG vectorization formats."""

    logger = logging.getLogger(__name__)

    def __init__(self):
        """Initializes the DataPrepForRag transformer instance."""
        pass

    def filter_low_value_count_rows(
        self, df: pd.DataFrame, column_name: str, min_count: int = 10
    ) -> pd.DataFrame:
        """Filters out rows where column value frequency is below min_count threshold.

        Args:
            df: Input DataFrame.
            column_name: Target column to compute value counts on.
            min_count: Minimum frequency threshold required to retain rows.

        Returns:
            Filtered DataFrame with rare categories excluded.
        """
        if df.empty or column_name not in df.columns:
            return df
        value_counts = df[column_name].value_counts()
        filtered_values = value_counts[value_counts >= min_count].index
        return df[df[column_name].isin(filtered_values)].copy()

    def process_rag_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms cleaned product records into standardized schema for RAG pipeline ingestion.

        Args:
            df: Preprocessed DataFrame output from DataPreprocessor.

        Returns:
            DataFrame schema-formatted and filtered specifically for RAG retrieval tasks.
        """
        working_df = df.rename(
            columns={
                "uniq_id": "Id",
                "product_name": "Name",
                "description": "Description",
                "brand": "Brand",
                "attributes": "Specifications",
            }
        ).copy()

        filtered_df = working_df[working_df["c0_name"] == "Clothing"]
        values_to_filter = ["Women's Clothing", "Men's Clothing", "Kids' Clothing"]
        clothing_filtered_df = filtered_df[
            filtered_df["c1_name"].isin(values_to_filter)
        ].copy()

        # Sequence data transformations safely to clean memory pointers
        c2_filtered_df = self.filter_low_value_count_rows(
            clothing_filtered_df, "c2_name", 10
        )
        c3_filtered_df = self.filter_low_value_count_rows(c2_filtered_df, "c3_name", 10)

        if c3_filtered_df.empty:
            return pd.DataFrame(
                columns=[
                    "Id",
                    "Name",
                    "Description",
                    "Brand",
                    "image",
                    "image_uri",
                    "c1_name",
                    "Specifications",
                ]
            )

        rag_df = c3_filtered_df[
            [
                "Id",
                "Name",
                "Description",
                "Brand",
                "image",
                "image_uri",
                "c1_name",
                "Specifications",
            ]
        ].copy()

        rag_df.drop_duplicates(inplace=True)

        rag_df["image_uri"] = rag_df["image_uri"].fillna("")
        rag_df["image"] = rag_df["image"].fillna("")
        rag_df["Description"] = rag_df["Description"].fillna("None")

        return rag_df
