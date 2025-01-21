# TODO : Use ray actors instead of task
import ray
import signal
import sys
import time
import os
import numpy as np
import logging
import importlib
import pandas as pd
from datapreprocessing import *
#from data_cleaner import DataPreprocessor
#from data_loader import DataLoader

# RAY_CLUSTER_HOST = os.environ["RAY_CLUSTER_HOST"]
# IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]

class RayUtils:

    logger = logging.getLogger(__name__)

    def __init__(self,ray_cluster_host,df,ray_resources,ray_runtime,package_name,module_name,class_name,method_name):
        self.ray_cluster_host = ray_cluster_host
        self.df = df
        self.ray_resource = ray_resources
        self.ray_runtime = ray_runtime
        self.module_name = module_name
        self.class_name = class_name
        self.method_name = method_name
        self.package_name = package_name


    # def split_dataframe(self, df, chunk_size=199):
    #     chunks = list()
    #     num_chunks = len(self.df) // self.chunk_size + 1
    #     for i in range(num_chunks):
    #         chunks.append(df[i * self.chunk_size : (i + 1) * self.chunk_size])
    #     return chunks
    
    @ray.remote(resources={"cpu": 1})
    def process_data(self, preprocessor, df, ray_worker_node_id):
        def func_not_found(): # just in case we dont have the function
            print ('No Function '+self.method_name+' Found!')
        func = getattr(self,self.method_name,func_not_found) 
        return preprocessor.func(df, ray_worker_node_id)

    def run_remote(self):
        # Read raw dataset from GCS
        #data_loader = DataLoader()
        #data_prep = DataPrep()

        # df = data_loader.load_raw_data(
        #     IMAGE_BUCKET, "flipkart_raw_dataset/flipkart_com-ecommerce_sample.csv"
        # )
        # df = df[
        #     [
        #         "uniq_id",
        #         "product_name",
        #         "description",
        #         "brand",
        #         "image",
        #         "product_specifications",
        #         "product_category_tree",
        #     ]
        # ]
        # print("Original dataset shape:", df.shape)
        # # Drop rows with null values in specified columns
        # df.dropna(
        #     subset=[
        #         "description",
        #         "image",
        #         "product_specifications",
        #         "product_category_tree",
        #     ],
        #     inplace=True,
        # )
        # print("After dropping null values:", df.shape)
        # Ray runtime env
        # runtime_env = {
        #     "pip": [
        #         "google-cloud-storage==2.16.0",
        #         "spacy==3.7.4",
        #         "jsonpickle==3.0.3",
        #         "pandas==2.2.1",
        #     ],
        #     "env_vars": {"PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        # }

        # Initiate a driver: start and connect with Ray cluster
        if self.ray_cluster_host != "local":
            ClientContext = ray.init(f"ray://{self.ray_cluster_host}", runtime_env=self.ray_runtime)
            self.logger.debug(ClientContext)

            # Get the ID of the node where the driver process is running
            driver_process_node_id = ray.get_runtime_context().get_node_id()  # HEX
            self.logger.debug(f"ray_driver_node_id={driver_process_node_id}")

            self.logger.debug(ray.cluster_resources())
        else:
            RayContext = ray.init()
            self.logger.debug(RayContext)

        # # Chunk the dataset
        # res = data_prep.split_dataframe(df)

        # Instantiate DataPreprocessor
        #preprocessor = DataPreprocessor()
        complete_module_name = self.package_name + "." + self.module_name
        module = importlib.import_module(complete_module_name)
        MyClass = getattr(module, self.class_name)
        preprocessor = MyClass()
        #TODO: make this comment generic
        self.logger.debug("Data Preparation started")
        start_time = time.time()
        results = ray.get([self.process_data.remote(preprocessor, df=self.df[i], ray_worker_node_id=i) for i in range(len(self.df))])
        duration = time.time() - start_time
        self.logger.debug(f"Data Preparation finished in {duration} seconds")

        # Disconnect the worker, and terminate processes started by ray.init()
        ray.shutdown()

        # concat all the resulting data frames
        result_df = pd.concat(results, axis=0, ignore_index=True)
        
        return result_df
        # # Replace NaN with None
        # result_df = result_df.replace({np.nan: None})

        # # Store the preprocessed data into GCS
        # result_df.to_csv(
        #     "gs://" + IMAGE_BUCKET + "/flipkart_preprocessed_dataset/flipkart.csv",
        #     index=False,
        # )
        # return result_df