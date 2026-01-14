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

import csv
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

# --- Configuration ---
llmd_endpoints_hostname = os.environ.get("llmd_endpoints_hostname", "localhost:7860")
URL = "https://" + llmd_endpoints_hostname + "/gradio_api/api/sync_chat"
TOKEN_FILE = "token.jwt"
MODEL = "Qwen/Qwen3-0.6B"

# STRESS SETTINGS
CONCURRENT_USERS = 100  # Massive increase to 100 users
TOTAL_REQUESTS = 5000  # Run longer
RESET_INTERVAL = 5  # Reset often to force new "Prefills" (the heavy operation)
LOG_FILE = "stress_test_heavy.csv"

# Shared counter
request_counter = 0
counter_lock = threading.Lock()


def get_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def generate_long_prompt(user_id):
    """
    Generates a ~4000 char prompt (~1000 tokens) to fill GPU Memory.
    """
    base_text = f"User {user_id} is running a stress test. "
    # Repeat this sentence 100 times to create a large block of text
    long_context = base_text * 150
    return f"Here is a large block of text:\n\n{long_context}\n\nTask: Summarize the above text in one sentence."


def run_user_session(user_id):
    global request_counter
    token = get_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    history = []

    while True:
        with counter_lock:
            if request_counter >= TOTAL_REQUESTS:
                break
            current_iter = request_counter + 1
            request_counter += 1

        # Reset Logic
        if len(history) >= RESET_INTERVAL:
            history = []

        # Message Logic
        if len(history) == 0:
            # TURN 1: SEND THE "BOMB" (Huge Prompt)
            current_message = generate_long_prompt(user_id)
        else:
            # TURN 2+: Short follow up to keep the memory occupied
            current_message = "Tell me more details."

        payload = {"data": [current_message, history, MODEL]}

        try:
            start_time = time.time()
            response = requests.post(URL, headers=headers, json=payload)
            duration = time.time() - start_time

            status = response.status_code

            # Log simple status
            with open(LOG_FILE, mode="a", newline="") as f:
                csv.writer(f).writerow(
                    [current_iter, user_id, len(history), f"{duration:.4f}", status]
                )

            # Print only if slow (filtering out the noise)
            if duration > 2.0 or status != 200:
                print(
                    f"[Req {current_iter}] User {user_id} | Latency: {duration:.2f}s | Status: {status}"
                )

        except Exception as e:
            print(f"User {user_id} Error: {e}")
            time.sleep(1)


def main():
    # Init CSV
    with open(LOG_FILE, mode="w", newline="") as f:
        csv.writer(f).writerow(
            ["Request_ID", "User_ID", "Turn_Num", "Latency", "Status"]
        )

    print(
        f"Starting HEAVY LOAD Stress Test: {CONCURRENT_USERS} Users sending 4KB prompts..."
    )

    with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [
            executor.submit(run_user_session, i) for i in range(CONCURRENT_USERS)
        ]
        for f in futures:
            f.result()


if __name__ == "__main__":
    main()
