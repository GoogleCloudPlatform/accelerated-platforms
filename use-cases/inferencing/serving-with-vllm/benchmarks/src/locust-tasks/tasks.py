#!/usr/bin/env python

# Copyright 2022 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from datetime import datetime
from locust import FastHttpUser, TaskSet, task, between
import logging
import logging.config
import os
import signal
import requests

def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)

# [START locust_test_task]

class MetricsTaskSet(TaskSet):

    def __init__(self):  # Constructor
        self.model_id = os.environ["MODEL_ID"]
        self.endpoint = os.environ["ENDPOINT"]
        #self.host = os.environ["HOST"]
        self.message1 = ( "I'm looking for comfortable cycling shorts for women, what are some good options?")
        self.message2 = "Tell me about some tops for men, looking for different styles"

    wait_time = between(1, 5)
    

    @task(50)
    def test1(self):
        headers = {'content-type': 'application/json'}
        r = self.rest("POST","/v1/chat/completions",json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": self.message1}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },headers=headers)
        print("FROM MESSAGE 1",r)

    @task(50)
    def test2(self):
        headers = {'content-type': 'application/json'}
        r = self.rest("POST","/v1/chat/completions",json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": self.message2}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },headers=headers) 
        print("FROM MESSAGE 2",r)       



class MetricsLocust(FastHttpUser):
    tasks = {MetricsTaskSet}

# [END locust_test_task]
