# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from locust import FastHttpUser, task, between
import os

model_id = os.environ["MODEL_ID"]

message1 = (
    "I'm looking for comfortable cycling shorts for women, what are some good options?"
)
message2 = "Tell me about some tops for men, looking for different styles"


class TestUser(FastHttpUser):
    wait_time = between(1, 5)

    @task(50)
    def test1(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": message1}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            name="message1",
        )

    @task(50)
    def test2(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": message2}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            name="message2",
        )
