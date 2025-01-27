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

# from data_cleaner import DataPreprocessor
# from data_loader import DataLoader

# RAY_CLUSTER_HOST = os.environ["RAY_CLUSTER_HOST"]
# IMAGE_BUCKET = os.environ["PROCESSING_BUCKET"]
# IMAGE_BUCKET = "gkebatchexpce3c8dcb-gushob-rag-data"
class RayUtils:
    """
    A utility class for distributing data processing tasks using Ray.

    Attributes:
        ray_cluster_host (str): The address of the Ray cluster.  Use "local" for local execution.
        ray_resources (dict): Resource requirements for Ray actors.
        ray_runtime (dict): Runtime environment configuration for Ray.
        package_name (str): The name of the Python package containing the processing class.
        module_name (str): The name of the Python module containing the processing class.
        class_name (str): The name of the class to instantiate for data processing.
        method_name (str): The name of the method to call for data processing. This method will be run as a ray task.
        df (list of pd.DataFrames): A list of Pandas DataFrames.
        gcs_bucket (str): The name of the Google Cloud Storage bucket used for data storage.
        logger (logging.Logger): A logger object for logging information and errors.

    Methods:
        run_remote(): Initiate a ray connection and runs the data processing tasks remotely using Ray.
        invoke_process_data(self, preprocessor, df, ray_worker_node_id, gcs_bucket): Invokes the data processing method as a task on Ray workers.
    """
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        ray_cluster_host,
        ray_resources,
        ray_runtime,
        package_name,
        module_name,
        class_name,
        method_name,
        df,
        gcs_bucket,
    ):
        self.ray_cluster_host = ray_cluster_host
        self.ray_resource = ray_resources
        self.ray_runtime = ray_runtime
        self.module_name = module_name
        self.class_name = class_name
        self.method_name = method_name
        self.package_name = package_name
        self.df = df
        self.gcs_bucket = gcs_bucket

    @ray.remote(resources={"cpu": 1})
    def invoke_process_data(self, preprocessor, df, ray_worker_node_id, gcs_bucket):
        """
        Invokes the specified data processing method on a Ray worker.

        Args:
            preprocessor (object): An instance of the data processing class.
            df (pd.DataFrame): The Pandas DataFrame to be processed.
            ray_worker_node_id (int): The ID of the Ray worker node.
            gcs_bucket (str): The name of the GCS bucket.

        Returns:
            pd.DataFrame: The processed Pandas DataFrame in this example. It returns the data returned by the function invoked as ray task.
        """
        def func_not_found():  # just in case we dont have the function
            print("No Function " + self.method_name + " Found!")

        func = getattr(preprocessor, self.method_name, func_not_found)
        # return preprocessor.process_data(df, ray_worker_node_id,IMAGE_BUCKET)
        return func(df, ray_worker_node_id, gcs_bucket)

    def run_remote(self):
        """
        Runs the data processing tasks remotely using Ray.  This method initializes the Ray cluster,
        imports the necessary modules and classes, instantiates the data processing class, and
        distributes the data processing tasks to Ray workers.

        Returns:
            pd.DataFrame: A concatenated Pandas DataFrame containing the results from all ray workers in this example. It returns the data returned by the function invoked as ray task.
        """
        # Initiate a driver: start and connect with Ray cluster
        if self.ray_cluster_host != "local":
            ClientContext = ray.init(
                f"ray://{self.ray_cluster_host}", runtime_env=self.ray_runtime
            )
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
        preprocessor = MyClass()
        # preprocessor = datacleaner.DataPreprocessor()
        # TODO: make this comment generic
        self.logger.debug("Data Preparation started")
        start_time = time.time()
        # results = ray.get([self.process_data.remote(preprocessor=preprocessor, df=self.df[i], ray_worker_node_id=i) for i in range(len(self.df))])
        results = ray.get(
            [
                self.invoke_process_data.remote(
                    self, preprocessor, self.df[i], i, self.gcs_bucket
                )
                for i in range(len(self.df))
            ]
        )
        # self_ref = ray.put(self)
        # results = ray.get([self.invoke_process_data.remote(self,preprocessor, self.df[i], i,IMAGE_BUCKET) for i in range(len(self.df))])
        duration = time.time() - start_time
        self.logger.debug(f"Data Preparation finished in {duration} seconds")

        # Disconnect the worker, and terminate processes started by ray.init()
        ray.shutdown()

        # concat all the resulting data frames
        result_df = pd.concat(results, axis=0, ignore_index=True)

        return result_df
