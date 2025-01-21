import os
import re
import socket
import urllib.error
import urllib.request
import jsonpickle
import spacy
import pandas as pd
from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY
from typing import List
import logging

#TODO : Bring consistency in passwing around these constants, Either pass them to each class whuile instantiating them ro read them from env in each class
#IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]
GCS_IMAGE_FOLDER = "flipkart_images"

class DataPreprocessor:

    logger = logging.getLogger(__name__)

    def __init__(self):
        pass

    def extract_url(self, image_list: str) -> List[str]:
        return image_list.replace("[", "").replace("]", "").replace('"', "").split(",")

    def download_image(self, image_url, image_file_name, destination_blob_name, ray_worker_node_id,gcs_bucket):
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

            #bucket = storage_client.bucket(IMAGE_BUCKET)
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

    def prep_product_desc(self, df):
        spacy.cli.download("en_core_web_sm")
        model = spacy.load("en_core_web_sm")

        def parse_nlp_description(description) -> str:
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

    def parse_attributes(self, specification: str):
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

    def get_product_image(self, df, ray_worker_node_id,gcs_bucket):
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
                destination_blob_name = f"{GCS_IMAGE_FOLDER}/{id}_{index}.jpg"
                image_found_flag = self.download_image(
                    image_url, image_file_name, destination_blob_name, ray_worker_node_id,gcs_bucket
                )
                if image_found_flag:
                    gcs_image_url.append(
                        #"gs://" + IMAGE_BUCKET + "/" + destination_blob_name
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
        if pd.isnull(text):
            return ""
        return text.replace("[", "").replace("]", "").replace('"', "")

    def prep_cat(self, df: pd.DataFrame) -> pd.DataFrame:
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

    def process_data(self, df, ray_worker_node_id, gcs_bucket):
        df_with_gcs_image_uri = self.get_product_image(df, ray_worker_node_id,gcs_bucket)
        df_with_desc = self.prep_product_desc(df_with_gcs_image_uri)
        df_with_desc["attributes"] = df_with_desc["product_specifications"].apply(self.parse_attributes)
        df_with_desc = df_with_desc.drop("product_specifications", axis=1)
        result_df = self.prep_cat(df_with_desc)
        return result_df