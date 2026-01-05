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
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

# --- Configuration ---
URL = "https://llmd.llm-d.inf-llm-d.endpoints.accelerated-platforms-dev.cloud.goog/api/chat"
TOKEN_FILE = "token.jwt"
MODEL = "Qwen/Qwen3-0.6B"
SYSTEM_INSTRUCTION = "[System Note: You are a helpful assistant. Answer directly and concisely. Do not show your reasoning or internal thoughts.]\n\n"

# STRESS SETTINGS
CONCURRENT_USERS = 50  # Number of parallel threads (Simulated Users)
TOTAL_REQUESTS = 1000  # Total requests to distribute across users
RESET_INTERVAL = 10  # Reset history every 10 turns per user
LOG_FILE = "stress_test_parallel.csv"

TOPICS = [
    "Write a Python function to calculate Fibonacci numbers.",
    "Explain the history of the Roman Empire briefly.",
    "What are the ingredients for a classic Omelette?",
    "Explain the theory of relativity to a 5 year old.",
    "Write a haiku about cloud computing.",
    "What are the best practices for Kubernetes networking.",
    "Tell me a joke about a database administrator.",
]

# Shared counter for logging
request_counter = 0
counter_lock = threading.Lock()


def get_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def clean_response(text):
    if not isinstance(text, str):
        return str(text)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


# This function represents ONE user session
def run_user_session(user_id):
    global request_counter
    token = get_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    history = []
    topic_index = user_id % len(TOPICS)  # Give each user a different starting topic

    while True:
        # Check if we hit global limit
        with counter_lock:
            if request_counter >= TOTAL_REQUESTS:
                break
            current_iter = request_counter + 1
            request_counter += 1

        # Reset Logic
        if len(history) >= RESET_INTERVAL:
            history = []
            topic_index = (topic_index + 1) % len(TOPICS)

        # Message Logic
        if len(history) == 0:
            current_message = SYSTEM_INSTRUCTION + TOPICS[topic_index]
        else:
            current_message = f"Tell me more. (User {user_id}, Turn {len(history)+1})"

        payload = {"data": [current_message, history, MODEL]}

        try:
            start_time = time.time()
            response = requests.post(URL, headers=headers, json=payload)
            duration = time.time() - start_time

            status = response.status_code
            clean_len = 0

            if status == 200:
                raw = response.json().get("data", [""])[0]
                cleaned = clean_response(raw)
                clean_len = len(cleaned)
                history.append([current_message, cleaned])

            # Log to CSV (Thread Safe Append)
            with open(LOG_FILE, mode="a", newline="") as f:
                csv.writer(f).writerow(
                    [
                        current_iter,
                        user_id,
                        len(history),
                        f"{duration:.4f}",
                        clean_len,
                        status,
                    ]
                )

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
            ["Request_ID", "User_ID", "Turn_Num", "Latency", "Len", "Status"]
        )

    print(
        f"Starting PARALLEL Stress Test: {CONCURRENT_USERS} Users, Target {TOTAL_REQUESTS} total requests."
    )

    with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        # Launch the users
        futures = [
            executor.submit(run_user_session, i) for i in range(CONCURRENT_USERS)
        ]

        # Wait for all to finish
        for f in futures:
            f.result()

    print("Test Complete.")


if __name__ == "__main__":
    main()
