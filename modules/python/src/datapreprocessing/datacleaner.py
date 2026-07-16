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
import os
import re
import socket
import urllib.error
import urllib.request
from typing import List

import jsonpickle
import pandas as pd
import spacy
from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY


class DataPreprocessor:
    """
    A class for preprocessing product data, including image downloading, text processing,
    and attribute parsing.

    Attributes:
        logger (logging.Logger): A logger object for logging information and errors.

    Methods:
        extract_url(image_list: str) -> List[str]: Extracts image URLs from a string.
        download_image(image_url, image_file_name, destination_blob_name, ray_worker_node_id, gcs_bucket): Downloads an image and uploads it to GCS.
        prep_product_desc(df): Prepares the product description by performing NLP preprocessing.
        parse_attributes(specification: str): Parses product specifications into a JSON string.
        get_product_image(df, ray_worker_node_id, gcs_bucket,gcs_folder): Downloads product images and adds their GCS URIs to the DataFrame.
        reformat(text: str) -> str: Reformats a string by removing brackets and quotes.
        prep_cat(df: pd.DataFrame) -> pd.DataFrame: Prepares product category information by splitting and cleaning the category tree.
        process_data(df, ray_worker_node_id, gcs_bucket): Performs the complete data preprocessing pipeline.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        pass

    def extract_url(self, image_list: str) -> List[str]:
        """
        Extracts image URLs from a string containing a comma-separated list of URLs.

        Args:
            image_list (str): A string containing a comma-separated list of image URLs, potentially with brackets and quotes.

        Returns:
            List[str]: A list of extracted image URLs.
        """
        return image_list.replace("[", "").replace("]", "").replace('"', "").split(",")

    def download_image(
        self,
        image_url: str,
        image_file_name: str,
        destination_blob_name: str,
        ray_worker_node_id: int,
        gcs_bucket: str,
    ) -> bool:
        """
        Downloads an image from a URL and uploads it to Google Cloud Storage.

        Args:
            image_url (str): The URL of the image to download.
            image_file_name (str): The local file name to save the downloaded image as.
            destination_blob_name (str): The name of the blob in GCS to upload the image to.
            ray_worker_node_id (int): The ID of the Ray worker node (for logging).
            gcs_bucket (str): The name of the GCS bucket.

        Returns:
            bool: True if the image was downloaded and uploaded successfully, False otherwise.  Raises exceptions on errors.
        """
        storage_client = storage.Client()
        download_dir = "/tmp/images"
        try:
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
        except FileExistsError as err:
            self.logger.warning(f"Directory '{download_dir}' already exists")

        try:
            download_file = f"{download_dir}/{image_file_name}"

            socket.setdefaulttimeout(10)
            urllib.request.urlretrieve(image_url, download_file)
            bucket = storage_client.bucket(gcs_bucket)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_filename(download_file, retry=DEFAULT_RETRY)
            self.logger.info(
                f"ray_worker_node_id:{ray_worker_node_id} File {image_file_name} uploaded to {destination_blob_name}"
            )
            os.remove(download_file)
            return True
        except TimeoutError as err:
            self.logger.warning(
                f"ray_worker_node_id:{ray_worker_node_id} Image '{image_url}' request timeout"
            )
        except urllib.error.HTTPError as err:
            if err.code == 404:
                self.logger.warning(
                    f"ray_worker_node_id:{ray_worker_node_id} Image '{image_url}' not found"
                )
            elif err.code == 504:
                self.logger.warning(
                    f"ray_worker_node_id:{ray_worker_node_id} Image '{image_url}' gateway timeout"
                )
            else:
                self.logger.error(
                    f"ray_worker_node_id:{ray_worker_node_id} Unhandled HTTPError exception: {err}"
                )
        except urllib.error.URLError as err:
            self.logger.error(
                f"ray_worker_node_id:{ray_worker_node_id} URLError exception: {err}"
            )
        except Exception as err:
            self.logger.error(
                f"ray_worker_node_id:{ray_worker_node_id} Unhandled exception: {err}"
            )
            raise

        return False

    def prep_product_desc(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepares the product description by performing NLP preprocessing using spaCy.

        Args:
            df (pd.DataFrame): The input DataFrame containing the 'description' column.

        Returns:
            pd.DataFrame: The DataFrame with the preprocessed 'description' column.
        """
        spacy.cli.download("en_core_web_sm")
        model = spacy.load("en_core_web_sm")

        def parse_nlp_description(description: str) -> str:
            if not pd.isna(description):
                try:
                    doc = model(description.lower())
                    lemmas = []
                    for token in doc:
                        if (
                            token.lemma_ not in lemmas
                            and not token.is_stop
                            and token.is_alpha
                        ):
                            lemmas.append(token.lemma_)
                    return " ".join(lemmas)
                except:
                    self.logger.error("Unable to load spacy model")

        df["description"] = df["description"].apply(parse_nlp_description)
        return df

    def parse_attributes(self, specification: str) -> str:
        """
        Parses product specifications from a string into a JSON string.

        Args:
            specification (str): A string containing the product specifications.

        Returns:
            str: A JSON string representing the parsed attributes, or None if the input is invalid or NaN.
        """
        spec_match_one = re.compile("(.*?)\\[(.*)\\](.*)")
        spec_match_two = re.compile('(.*?)=>"(.*?)"(.*?)=>"(.*?)"(.*)')
        if pd.isna(specification):
            return None
        m = spec_match_one.match(specification)
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
        json_string = jsonpickle.encode(out)
        return json_string

    def get_product_image(
        self,
        df: pd.DataFrame,
        ray_worker_node_id: int,
        gcs_bucket: str,
        gcs_folder: str,
    ) -> pd.DataFrame:
        """
        Downloads product images for each product in the DataFrame and adds the GCS URI to a new 'image_uri' column.

        Args:
            df (pd.DataFrame): The input DataFrame containing product information and image URLs.
            ray_worker_node_id (int): The ID of the Ray worker node (for logging).
            gcs_bucket (str): The name of the GCS bucket.
            gcs_folder (str): The folder in the GCS bucket where the images will be stored.

        Returns:
            pd.DataFrame: The DataFrame with the added 'image_uri' column.
        """
        products_with_no_image_count = 0
        products_with_no_image = []
        gcs_image_url = []

        image_found_flag = False
        for id, image_list in zip(df["uniq_id"], df["image"]):

            if pd.isnull(image_list):  # No image url
                self.logger.warning(f"No image url for product {id}")
                products_with_no_image_count += 1
                products_with_no_image.append(id)
                gcs_image_url.append(None)
                continue
            image_urls = self.extract_url(image_list)
            for index in range(len(image_urls)):
                image_url = image_urls[index].strip()
                image_file_name = f"{id}_{index}.jpg"
                destination_blob_name = f"{gcs_folder}/{id}_{index}.jpg"
                image_found_flag = self.download_image(
                    image_url,
                    image_file_name,
                    destination_blob_name,
                    ray_worker_node_id,
                    gcs_bucket,
                )
                if image_found_flag:
                    gcs_image_url.append(
                        "gs://" + gcs_bucket + "/" + destination_blob_name
                    )
                    break
            if not image_found_flag:
                self.logger.warning(f"No image found for product {id}")
                products_with_no_image_count += 1
                products_with_no_image.append(id)
                gcs_image_url.append(None)

        # appending gcs image uri into dataframe
        gcs_image_loc = pd.DataFrame(gcs_image_url, index=df.index)
        gcs_image_loc.columns = ["image_uri"]
        df_with_gcs_image_uri = pd.concat([df, gcs_image_loc], axis=1)
        return df_with_gcs_image_uri

    def reformat(self, text: str) -> str:
        """
        Reformats a string by removing square brackets and double quotes.

        Args:
            text (str): The string to reformat.

        Returns:
            str: The reformatted string, or an empty string if the input is NaN.
        """
        if pd.isnull(text):
            return ""
        return text.replace("[", "").replace("]", "").replace('"', "")

    def prep_cat(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepares product category information by splitting the 'product_category_tree' column into separate category levels.

        Args:
            df (pd.DataFrame): The input DataFrame containing the 'product_category_tree' column.

        Returns:
            pd.DataFrame: The DataFrame with the added category level columns.
        """
        df["product_category_tree"] = df["product_category_tree"].apply(
            lambda x: self.reformat(x)
        )
        temp_df = df["product_category_tree"].str.split(">>", expand=True)
        max_splits = temp_df.shape[1]  # Get the number of columns after splitting
        # Create column names dynamically
        column_names = [f"c{i}_name" for i in range(max_splits)]
        temp_df.columns = column_names
        for col in temp_df.columns:
            temp_df[col] = temp_df[col].apply(lambda x: x.strip() if x else x)
        # concatenating df1 and df2 along rows
        df_with_cat = pd.concat([df, temp_df], axis=1)
        df_with_cat = df_with_cat.drop("product_category_tree", axis=1)
        return df_with_cat

    def process_data(
        self,
        df: pd.DataFrame,
        ray_worker_node_id: int,
        gcs_bucket: str,
        gcs_folder: str,
    ) -> pd.DataFrame:
        """
        Performs the complete data preprocessing pipeline, including image downloading, description preprocessing,
        attribute parsing, and category preparation.

        Args:
            df (pd.DataFrame): The input DataFrame.
            ray_worker_node_id (int): The ID of the Ray worker node (for logging).
            gcs_bucket (str): The name of the GCS bucket.
            gcs_folder (str): The folder in the GCS bucket where the images will be stored.

        Returns:
            pd.DataFrame: The preprocessed DataFrame.
        """
        df_with_gcs_image_uri = self.get_product_image(
            df, ray_worker_node_id, gcs_bucket, gcs_folder
        )
        df_with_desc = self.prep_product_desc(df_with_gcs_image_uri)
        df_with_desc["attributes"] = df_with_desc["product_specifications"].apply(
            self.parse_attributes
        )
        df_with_desc = df_with_desc.drop("product_specifications", axis=1)
        result_df = self.prep_cat(df_with_desc)
        return result_df


class DataPrepForRag:
    """
    A class for preparing data specifically for use with a Retrieval Augmented Generation (RAG) system.

    Attributes:
        logger (logging.Logger): A logger object for logging information and errors.

    Methods:
        filter_low_value_count_rows(df, column_name, min_count=10): Filters rows based on minimum value counts in a column.
        process_rag_input(df): Processes the input DataFrame for RAG, including renaming columns, filtering, and selecting relevant columns.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        pass

    def filter_low_value_count_rows(
        self, df: pd.DataFrame, column_name: str, min_count: int = 10
    ) -> pd.DataFrame:
        """
        Removes rows from a DataFrame where the value count in the specified column is less than the given minimum count.

        Args:
            df (pd.DataFrame): The Pandas DataFrame to filter.
            column_name (str): The name of the column to check value counts for.
            min_count (int, optional): The minimum value count required for a row to be kept. Defaults to 10.

        Returns:
            pd.DataFrame: A new DataFrame with rows removed where value counts are below the threshold.
        """

        # Calculate value counts for the specified column
        value_counts = df[column_name].value_counts()

        # Filter values that meet the minimum count criteria
        filtered_values = value_counts[value_counts >= min_count].index

        # Create a new DataFrame keeping only rows with those values
        filtered_df = df[df[column_name].isin(filtered_values)]

        return filtered_df

    def process_rag_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes the input DataFrame to prepare it for use with a RAG system.  This includes renaming columns,
        filtering data based on categories and value counts, selecting relevant columns, and removing duplicates.

        Args:
            df (pd.DataFrame): The input DataFrame.

        Returns:
            pd.DataFrame: The processed DataFrame ready for RAG.
        """
        # renaming column name
        df.rename(
            columns={
                "uniq_id": "Id",
                "product_name": "Name",
                "description": "Description",
                "brand": "Brand",
                "attributes": "Specifications",
            },
            inplace=True,
        )
        # filtering clothings for men, women and kids
        filtered_df = df[df["c0_name"] == "Clothing"]
        values_to_filter = ["Women's Clothing", "Men's Clothing", "Kids' Clothing"]
        clothing_filtered_df = filtered_df[
            filtered_df["c1_name"].isin(values_to_filter)
        ]
        # Filter to keep rows where 'c2_name' has count >=10
        c2_filtered_df = self.filter_low_value_count_rows(
            clothing_filtered_df, "c2_name", 10
        )
        # Filter to keep rows where 'c3_name' has count >=10
        c3_filtered_df = self.filter_low_value_count_rows(
            clothing_filtered_df, "c3_name", 10
        )
        # prep RA df with subset of the columns
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
        ]
        # Drop duplicates
        rag_df.drop_duplicates(inplace=True)
        # Replace NaN with None
        rag_df["image_uri"] = df["image_uri"].fillna(value="")
        rag_df["image"] = df["image"].fillna(value="")
        rag_df["Description"] = df["Description"].fillna(value="None")
        return rag_df
