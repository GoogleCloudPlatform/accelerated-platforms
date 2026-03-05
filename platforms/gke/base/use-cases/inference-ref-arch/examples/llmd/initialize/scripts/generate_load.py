# Copyright 2025 Google LLC
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

import asyncio
import os
import random

import aiohttp

llmd_endpoints_hostname = os.environ.get("llmd_endpoints_hostname", "localhost:7860")
URL = "https://" + llmd_endpoints_hostname + "/gradio_api/api/sync_chat"
MODEL = os.environ.get("HF_MODEL_ID", "qwen/qwen3-32b")
TOKEN_FILE = "token.jwt"
print(f"Preparing to send the requests to the MODEL {MODEL}")
CONCURRENT_USERS = 50
TOTAL_REQUESTS = 1000
THINK_TIME = 2.0
RAMP_UP_DELAY = 0.5


def get_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "dummy-token"


def generate_light_prompt():
    """Generates a short, simple prompt to keep Pre-fill time (TTFT) low."""
    topics = [
        "the weather",
        "cooking pasta",
        "how bees fly",
        "the moon",
        "why sky is blue",
    ]
    return f"Tell me a very short fun fact about {random.choice(topics)}."


async def run_user_session(session, user_id, semaphore, headers):
    global request_counter

    # Staggered Start: Don't let everyone hit the server at second 0.0
    await asyncio.sleep(user_id * RAMP_UP_DELAY)

    async with semaphore:
        while True:
            # Atomic-style check for total requests
            if globals()["request_counter"] >= TOTAL_REQUESTS:
                break

            globals()["request_counter"] += 1
            current_message = generate_light_prompt()

            # Using empty history to keep the KV Cache small/fast
            payload = {"data": [current_message, [], MODEL]}

            try:
                async with session.post(URL, headers=headers, json=payload) as response:
                    await response.text()
                    print(f"User {user_id:02d} | Status: {response.status}")

            except Exception as e:
                print(f"Connection error for User {user_id}: {e}")

            # "Think Time" - Relax the backend between bursts
            await asyncio.sleep(random.uniform(1, THINK_TIME))


request_counter = 0


async def main():
    print(f"Starting RELAXED Load: {CONCURRENT_USERS} concurrent users...")
    token = get_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    connector = aiohttp.TCPConnector(limit=CONCURRENT_USERS)
    timeout = aiohttp.ClientTimeout(total=30)
    semaphore = asyncio.Semaphore(CONCURRENT_USERS)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for i in range(CONCURRENT_USERS):
            tasks.append(
                asyncio.create_task(run_user_session(session, i, semaphore, headers))
            )

        await asyncio.gather(*tasks)
    print("Test Complete.")


if __name__ == "__main__":
    asyncio.run(main())
