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
    def invoke_process_data(self, preprocessor, df, ray_worker_node_id):
        def func_not_found(): # just in case we dont have the function
            print ('No Function '+self.method_name+' Found!')
        #func = getattr(self,self.method_name,func_not_found) 
        func = getattr(preprocessor,self.method_name,func_not_found) 
        return preprocessor.func(df, ray_worker_node_id)

    def run_remote(self):
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

        complete_module_name = self.package_name + "." + self.module_name
        module = importlib.import_module(complete_module_name)
        MyClass = getattr(module, self.class_name)
        self.preprocessor = MyClass()
        #TODO: make this comment generic
        self.logger.debug("Data Preparation started")
        start_time = time.time()
        #results = ray.get([self.process_data.remote(preprocessor=preprocessor, df=self.df[i], ray_worker_node_id=i) for i in range(len(self.df))])
        results = ray.get([self.invoke_process_data.remote(preprocessor=self.preprocessor, df=self.df[i], ray_worker_node_id=i) for i in range(len(self.df))])
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