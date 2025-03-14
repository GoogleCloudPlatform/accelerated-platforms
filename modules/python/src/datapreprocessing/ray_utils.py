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

import importlib
import logging
import os
import signal
import sys
import time
from typing import Any, Dict

import numpy as np
import pandas as pd
import ray
from datapreprocessing import *


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
        ray_cluster_host: str,
        ray_resources: Dict[str, Any],
        ray_runtime: Dict[str, Any],
        package_name: str,
        module_name: str,
        class_name: str,
        method_name: str,
        df: pd.DataFrame,
        gcs_bucket: str,
        gcs_folder: str,
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
        self.gcs_folder = gcs_folder

    @ray.remote(resources={"cpu": 1})
    def invoke_process_data(
        self,
        preprocessor,
        df: pd.DataFrame,
        ray_worker_node_id: int,
        gcs_bucket: str,
        gcs_folder: str,
    ):
        """
        Invokes the specified data processing method on a Ray worker.

        Args:
            preprocessor (object): An instance of the data processing class.
            df (pd.DataFrame): The Pandas DataFrame to be processed.
            ray_worker_node_id (int): The ID of the Ray worker node.
            gcs_bucket (str): The name of the GCS bucket.
            gcs_folder (str): The folder in the GCS bucket where the images will be stored.

        Returns:
            pd.DataFrame: The processed Pandas DataFrame in this example. It returns the data returned by the function invoked as ray task.
        """

        def func_not_found():  # just in case we don't have the function
            print("No Function " + self.method_name + " Found!")

        func = getattr(preprocessor, self.method_name, func_not_found)
        return func(df, ray_worker_node_id, gcs_bucket, gcs_folder)

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
        # Probably make this comment generic since any function can be passed to rayutil for running as a task
        self.logger.debug("Data Preparation started")
        start_time = time.time()
        results = ray.get(
            [
                self.invoke_process_data.remote(
                    self, preprocessor, self.df[i], i, self.gcs_bucket, self.gcs_folder
                )
                for i in range(len(self.df))
            ]
        )
        duration = time.time() - start_time
        self.logger.debug(f"Data Preparation finished in {duration} seconds")

        # Disconnect the worker, and terminate processes started by ray.init()
        ray.shutdown()

        # concat all the resulting data frames
        result_df = pd.concat(results, axis=0, ignore_index=True)

        return result_df
