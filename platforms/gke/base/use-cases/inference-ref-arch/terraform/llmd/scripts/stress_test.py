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
import time

import aiohttp

llmd_endpoints_hostname = os.environ.get("llmd_endpoints_hostname", "localhost:7860")
URL = "https://" + llmd_endpoints_hostname + "/gradio_api/api/sync_chat"
MODEL = "Qwen/Qwen3-0.6B"
TOKEN_FILE = "token.jwt"

CONCURRENT_USERS = 500  # Exact number of simultaneous requests
TOTAL_REQUESTS = 5000  # Run until this many total requests finish
RESET_INTERVAL = 5000  # Reset history rarely to keep context large
request_counter = 0


def get_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"The token file '{TOKEN_FILE}' was not found!")
        raise RuntimeError()


def generate_long_prompt(user_id):
    """Generates a ~4000 char prompt to ensure heavy processing."""
    base_text = f"User {user_id} is stressing the queue. "
    long_context = base_text * 150
    return f"Here is a large block of text:\n\n{long_context}\n\nTask: Summarize the above text in one sentence."


async def run_user_session(session, user_id, semaphore):
    global request_counter

    token = get_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    history = []

    # The semaphore ensures exactly CONCURRENT_USERS are active at once
    async with semaphore:
        while True:
            # Check global counter
            if request_counter >= TOTAL_REQUESTS:
                break

            # Increment Global Counter
            current_iter = request_counter + 1
            request_counter += 1

            # Logic: Reset History
            if len(history) >= RESET_INTERVAL:
                history = []

            # Logic: Message Content
            if len(history) == 0:
                current_message = generate_long_prompt(user_id)
            else:
                current_message = "Tell me more details."

            payload = {"data": [current_message, history, MODEL]}

            try:
                async with session.post(URL, headers=headers, json=payload) as response:
                    await response.text()
                    status = response.status
                    print(f"[Req {current_iter}] User {user_id} | Status: {status}")

            except Exception as e:
                pass


async def main():
    print(f"Starting QUEUE FILL Test: {CONCURRENT_USERS} Simultaneous Users...")
    connector = aiohttp.TCPConnector(limit=0, force_close=False, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=None)
    # Semaphore: Strict limit of 2000 active tasks
    semaphore = asyncio.Semaphore(CONCURRENT_USERS)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for i in range(CONCURRENT_USERS):
            task = asyncio.create_task(run_user_session(session, i, semaphore))
            tasks.append(task)

        # No sleep/ramp-up here. Launch everything instantly.
        print("Launching requests...")
        await asyncio.gather(*tasks)
    print("Test Complete.")


if __name__ == "__main__":
    asyncio.run(main())
